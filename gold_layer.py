
import sys

from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "S3_BUCKET_NAME", "SILVER_DATABASE"]
)

BUCKET = args["S3_BUCKET_NAME"]
SILVER_DATABASE = args["SILVER_DATABASE"]

GOLD_PATH = f"s3://{BUCKET}/gold/"

# --------------------------------------------------
# INITIALIZE
# --------------------------------------------------

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

def read_silver(table_name):
    dyf = glueContext.create_dynamic_frame.from_catalog(
        database=SILVER_DATABASE,
        table_name=table_name,
        transformation_ctx=f"silver_{table_name}"
    )
    return dyf.toDF()

def write_gold(df, table_name):
    path = f"{GOLD_PATH}{table_name}/"

    (
        df.write
        .mode("overwrite")
        .format("parquet")
        .save(path)
    )

    print(f"Gold output written: {table_name}")

# --------------------------------------------------
# 1. READ SILVER TABLES
# --------------------------------------------------

sales = read_silver("sales")
products = read_silver("products")
inventory = read_silver("inventory")
suppliers = read_silver("suppliers")

# --------------------------------------------------
# 2. DAILY PRODUCT SALES AGGREGATION
# --------------------------------------------------

sales = (
    sales
    .withColumn(
        "product_id",
        F.col("StockCode").cast("string")
    )
    .withColumn(
        "transaction_date",
        F.to_date("transaction_date")
    )
    .withColumn(
        "Quantity",
        F.col("Quantity").cast("double")
    )
    .withColumn(
        "Price",
        F.col("Price").cast("double")
    )
)

daily_sales = (
    sales
    .groupBy("product_id", "transaction_date")
    .agg(
        F.sum("Quantity").alias("units_sold"),
        F.sum(F.col("Quantity") * F.col("Price")).alias("revenue"),
        F.avg("Price").alias("average_selling_price"),
        F.countDistinct("Invoice").alias("invoice_count")
    )
)

if daily_sales.limit(1).count() == 0:
    raise ValueError("No valid sales data found. Gold ETL cannot continue.")

# --------------------------------------------------
# 3. CREATE COMPLETE PRODUCT-DATE GRID
# --------------------------------------------------

# Include all products from the product dimension.
product_list = (
    products
    .select(F.col("product_id").cast("string").alias("product_id"))
    .filter(F.col("product_id").isNotNull())
    .dropDuplicates()
)

# Find the historical date range.
date_bounds = daily_sales.agg(
    F.min("transaction_date").alias("min_date"),
    F.max("transaction_date").alias("max_date")
).first()

min_date = date_bounds["min_date"]
max_date = date_bounds["max_date"]

if min_date is None or max_date is None:
    raise ValueError("Could not determine the sales date range.")

calendar = (
    spark
    .range(1)
    .select(
        F.explode(
            F.sequence(
                F.lit(min_date).cast("date"),
                F.lit(max_date).cast("date"),
                F.expr("INTERVAL 1 DAY")
            )
        ).alias("transaction_date")
    )
)

# Build product x calendar grid.
product_calendar = product_list.crossJoin(calendar)

daily_complete = (
    product_calendar
    .join(
        daily_sales,
        on=["product_id", "transaction_date"],
        how="left"
    )
    .fillna({
        "units_sold": 0.0,
        "revenue": 0.0,
        "average_selling_price": 0.0,
        "invoice_count": 0
    })
)

# --------------------------------------------------
# 4. SAVE DAILY PRODUCT SALES
# --------------------------------------------------

write_gold(daily_complete, "daily_product_sales")

# --------------------------------------------------
# 5. CREATE ML DEMAND FEATURES
# --------------------------------------------------

window_product = (
    Window
    .partitionBy("product_id")
    .orderBy("transaction_date")
)

# Rolling windows exclude the current day's target.
rolling_7 = window_product.rowsBetween(-7, -1)
rolling_28 = window_product.rowsBetween(-28, -1)

features = (
    daily_complete
    .withColumn("sales_lag_1", F.lag("units_sold", 1).over(window_product))
    .withColumn("sales_lag_7", F.lag("units_sold", 7).over(window_product))
    .withColumn("sales_lag_14", F.lag("units_sold", 14).over(window_product))
    .withColumn("sales_lag_28", F.lag("units_sold", 28).over(window_product))
    .withColumn(
        "rolling_mean_7",
        F.avg("units_sold").over(rolling_7)
    )
    .withColumn(
        "rolling_mean_28",
        F.avg("units_sold").over(rolling_28)
    )
    .withColumn(
        "rolling_std_7",
        F.stddev_pop("units_sold").over(rolling_7)
    )
    # ISO weekday convention: Monday=1, Sunday=7.
    .withColumn(
        "day_of_week",
        F.pmod(F.dayofweek("transaction_date") + F.lit(5), F.lit(7)) + F.lit(1)
    )
    .withColumn("month", F.month("transaction_date"))
    .withColumn("day_of_month", F.dayofmonth("transaction_date"))
    .withColumn("year", F.year("transaction_date"))
    .withColumn(
        "is_weekend",
        F.when(F.col("day_of_week").isin(6, 7), 1).otherwise(0)
    )
)

# Fill initial missing lag/rolling values with zero.
feature_columns = [
    "sales_lag_1",
    "sales_lag_7",
    "sales_lag_14",
    "sales_lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "rolling_std_7"
]

for column_name in feature_columns:
    features = features.withColumn(
        column_name,
        F.coalesce(F.col(column_name), F.lit(0.0))
    )

write_gold(features, "product_demand_features")

# --------------------------------------------------
# 6. INVENTORY ANALYTICS
# --------------------------------------------------

inventory_clean = (
    inventory
    .select(
        F.col("product_id").cast("string").alias("product_id"),
        F.col("supplier_id").cast("string").alias("supplier_id"),
        F.col("current_stock").cast("int").alias("current_stock"),
        F.col("safety_stock").cast("int").alias("safety_stock"),
        F.to_date("snapshot_date").alias("snapshot_date")
    )
)

supplier_clean = (
    suppliers
    .select(
        F.col("supplier_id").cast("string").alias("supplier_id"),
        "supplier_name",
        F.col("lead_time_days").cast("int").alias("lead_time_days"),
        F.col("minimum_order_quantity").cast("int").alias(
            "minimum_order_quantity"
        ),
        F.col("reorder_multiple").cast("int").alias("reorder_multiple")
    )
)

product_clean = (
    products
    .select(
        F.col("product_id").cast("string").alias("product_id"),
        "product_name",
        F.col("unit_price").cast("double").alias("unit_price")
    )
)

inventory_analytics = (
    inventory_clean
    .join(product_clean, on="product_id", how="left")
    .join(supplier_clean, on="supplier_id", how="left")
)

# Do not silently discard inventory records with missing supplier details.
missing_supplier_count = (
    inventory_analytics
    .filter(
        F.col("lead_time_days").isNull()
        | F.col("minimum_order_quantity").isNull()
        | F.col("reorder_multiple").isNull()
    )
    .count()
)

if missing_supplier_count > 0:
    raise ValueError(
        f"{missing_supplier_count} inventory records have missing supplier "
        "details. Check the Silver inventory and suppliers tables."
    )

write_gold(inventory_analytics, "inventory_analytics")

# --------------------------------------------------
# 7. VALIDATE GOLD OUTPUTS
# --------------------------------------------------

for table_name in [
    "daily_product_sales",
    "product_demand_features",
    "inventory_analytics"
]:
    df = spark.read.parquet(f"{GOLD_PATH}{table_name}/")
    print(f"Gold {table_name}: {df.count()} rows")
    df.printSchema()

job.commit()
print("Gold ETL completed.")
