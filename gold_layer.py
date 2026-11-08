import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import IntegerType, DoubleType

# Initialize Glue Context
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_BUCKET_NAME', 'GLUE_SILVER_DB', 'GLUE_GOLD_DB'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

s3_bucket = args['S3_BUCKET_NAME']
silver_db = args['GLUE_SILVER_DB']

# ==============================================================================
# 1. READ SILVER CLEAN TRANSACTIONS
# ==============================================================================
silver_retail_df = glueContext.create_dynamic_frame.from_catalog(
    database=silver_db,
    table_name="online_retail"
).toDF()

# Filter for valid sales (exclude cancellations and negative return quantities)
valid_sales_df = silver_retail_df.filter(
    (F.col("is_cancellation") == False) & 
    (F.col("is_return") == False) & 
    (F.col("Quantity") > 0)
)

# Aggregate daily sales per product
daily_agg_df = valid_sales_df.groupBy("StockCode", "transaction_date") \
    .agg(
        F.sum("Quantity").alias("units_sold"),
        F.sum(F.col("Quantity") * F.col("Price")).alias("total_revenue"),
        F.avg("Price").alias("avg_daily_price")
    )

# ==============================================================================
# 2. GENERATE COMPLETE PRODUCT-DATE CALENDAR & ZERO-FILL
# ==============================================================================
# Calculate date bounds and total day count
date_stats = daily_agg_df.select(
    F.min("transaction_date").alias("min_date"),
    F.max("transaction_date").alias("max_date"),
    F.datediff(F.max("transaction_date"), F.min("transaction_date")).alias("day_count")
).collect()[0]

min_date = date_stats["min_date"]
day_count = date_stats["day_count"]

# Get distinct products
distinct_products = daily_agg_df.select("StockCode").distinct()

# Generate continuous date grid using spark.range and date_add (bulletproof across Spark versions)
date_sequence_df = spark.range(0, day_count + 1).select(
    F.date_add(F.lit(min_date), F.col("id").cast("int")).alias("transaction_date")
)

# Cross join products with date sequence to build full grid
full_grid_df = distinct_products.crossJoin(date_sequence_df)

# Left join aggregated sales with full grid and fill missing dates with 0
daily_product_sales = full_grid_df.join(
    daily_agg_df, on=["StockCode", "transaction_date"], how="left"
).fillna({
    "units_sold": 0,
    "total_revenue": 0.0
})

# Write daily_product_sales to S3 Gold
daily_product_sales.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/gold/daily_product_sales/")

# ==============================================================================
# 3. FEATURE ENGINEERING FOR DEMAND FORECASTING
# ==============================================================================
# Define Window ordered by date per product
product_window = Window.partitionBy("StockCode").orderBy("transaction_date")

# Define rolling windows (excluding current day target date: -N to -1)
rolling_7_window = product_window.rowsBetween(-7, -1)
rolling_28_window = product_window.rowsBetween(-28, -1)

gold_features_df = daily_product_sales \
    .withColumn("sales_lag_1", F.lag("units_sold", 1).over(product_window)) \
    .withColumn("sales_lag_7", F.lag("units_sold", 7).over(product_window)) \
    .withColumn("sales_lag_14", F.lag("units_sold", 14).over(product_window)) \
    .withColumn("sales_lag_28", F.lag("units_sold", 28).over(product_window)) \
    .withColumn("rolling_mean_7", F.avg("units_sold").over(rolling_7_window)) \
    .withColumn("rolling_mean_28", F.avg("units_sold").over(rolling_28_window)) \
    .withColumn("rolling_std_7", F.stddev("units_sold").over(rolling_7_window)) \
    .withColumn("day_of_week", F.dayofweek("transaction_date")) \
    .withColumn("month", F.month("transaction_date")) \
    .withColumn("is_weekend", F.when(F.col("day_of_week").isin(1, 7), 1).otherwise(0))

# Write product_demand_features to S3 Gold
gold_features_df.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/gold/product_demand_features/")

# ==============================================================================
# 4. INVENTORY ANALYTICS TABLE
# ==============================================================================
silver_inventory_df = glueContext.create_dynamic_frame.from_catalog(
    database=silver_db,
    table_name="inventory"
).toDF()

silver_suppliers_df = glueContext.create_dynamic_frame.from_catalog(
    database=silver_db,
    table_name="suppliers"
).toDF()

inventory_analytics_df = silver_inventory_df.join(
    silver_suppliers_df, on="supplier_id", how="left"
).select(
    F.col("product_id"),
    F.col("supplier_id"),
    F.col("current_stock"),
    F.col("safety_stock"),
    F.col("lead_time_days"),
    F.col("minimum_order_quantity"),
    F.col("reorder_multiple"),
    F.col("snapshot_date")
)

inventory_analytics_df.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/gold/inventory_analytics/")

job.commit()