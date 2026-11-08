import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, DateType, TimestampType

# Initialize Glue Context
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_BUCKET_NAME', 'GLUE_DATABASE'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

s3_bucket = args['S3_BUCKET_NAME']
glue_database = args['GLUE_DATABASE']

# ==============================================================================
# 1. PROCESS ONLINE RETAIL TRANSACTIONS
# Columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country
# ==============================================================================
# Enable legacy time parser policy to prevent strict formatting crashes in Spark 3.x
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")

# 1. PROCESS ONLINE RETAIL TRANSACTIONS
raw_retail_df = glueContext.create_dynamic_frame.from_catalog(
    database=glue_database,
    table_name="online_retail"
).toDF()

# Parse InvoiceDate trying ISO format first ('yyyy-MM-dd HH:mm:ss'), then fallback formats
cleaned_retail = raw_retail_df \
    .withColumn("Invoice", F.trim(F.col("Invoice"))) \
    .withColumn("StockCode", F.trim(F.upper(F.col("StockCode")))) \
    .withColumn("Description", F.trim(F.col("Description"))) \
    .withColumn("Quantity", F.col("Quantity").cast(IntegerType())) \
    .withColumn("Price", F.col("Price").cast(DoubleType())) \
    .withColumn("Customer ID", F.trim(F.col("Customer ID"))) \
    .withColumn("Country", F.trim(F.col("Country"))) \
    .withColumn("InvoiceDate_ts", F.coalesce(
        F.expr("try_to_timestamp(InvoiceDate, 'yyyy-MM-dd HH:mm:ss')"),
        F.expr("try_to_timestamp(InvoiceDate, 'yyyy-MM-dd HH:mm')"),
        F.expr("try_to_timestamp(InvoiceDate, 'M/d/yyyy H:m')"),
        F.expr("try_to_timestamp(InvoiceDate, 'd/M/yyyy H:m')")
    )) \
    .withColumn("transaction_date", F.to_date(F.col("InvoiceDate_ts"))) \
    .withColumn("is_cancellation", F.when(F.col("Invoice").startswith("C"), True).otherwise(False)) \
    .withColumn("is_return", F.when(F.col("Quantity") < 0, True).otherwise(False))

# Validation condition: StockCode cannot be null and Price must be >= 0
valid_retail_condition = (F.col("StockCode").isNotNull()) & (F.col("Price") >= 0.0)

valid_retail_df = cleaned_retail.filter(valid_retail_condition)
rejected_retail_df = cleaned_retail.filter(~valid_retail_condition) \
    .withColumn("rejection_reason", F.lit("Missing StockCode or negative Price"))

# Deduplicate based on composite key
silver_retail_df = valid_retail_df.dropDuplicates([
    "Invoice", "StockCode", "InvoiceDate_ts", "Quantity", "Price", "Customer ID"
])

# Write Clean Transactions to S3 Silver
silver_retail_df.write \
    .mode("overwrite") \
    .partitionBy("transaction_date") \
    .parquet(f"s3://{s3_bucket}/silver/online_retail/")

# Write Rejected Records to S3 Rejected audit location
rejected_retail_df.write \
    .mode("append") \
    .parquet(f"s3://{s3_bucket}/rejected/invalid_transactions/")

# ==============================================================================
# 2. PROCESS INVENTORY
# Columns: product_id, supplier_id, current_stock, safety_stock, snapshot_date
# ==============================================================================
raw_inventory_df = glueContext.create_dynamic_frame.from_catalog(
    database=glue_database,
    table_name="inventory"
).toDF()

silver_inventory_df = raw_inventory_df \
    .withColumn("product_id", F.trim(F.col("product_id"))) \
    .withColumn("supplier_id", F.trim(F.col("supplier_id"))) \
    .withColumn("current_stock", F.col("current_stock").cast(IntegerType())) \
    .withColumn("safety_stock", F.col("safety_stock").cast(IntegerType())) \
    .withColumn("snapshot_date", F.to_date(F.col("snapshot_date"))) \
    .filter(F.col("product_id").isNotNull()) \
    .dropDuplicates(["product_id", "snapshot_date"])

silver_inventory_df.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/silver/inventory/")

# ==============================================================================
# 3. PROCESS PRODUCTS
# Columns: product_id, product_name, unit_price
# ==============================================================================
raw_products_df = glueContext.create_dynamic_frame.from_catalog(
    database=glue_database,
    table_name="products"
).toDF()

silver_products_df = raw_products_df \
    .withColumn("product_id", F.trim(F.col("product_id"))) \
    .withColumn("product_name", F.trim(F.col("product_name"))) \
    .withColumn("unit_price", F.col("unit_price").cast(DoubleType())) \
    .filter(F.col("product_id").isNotNull()) \
    .dropDuplicates(["product_id"])

silver_products_df.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/silver/products/")

# ==============================================================================
# 4. PROCESS SUPPLIERS
# Columns: supplier_id, supplier_name, lead_time_days, minimum_order_quantity, reorder_multiple
# ==============================================================================
raw_suppliers_df = glueContext.create_dynamic_frame.from_catalog(
    database=glue_database,
    table_name="suppliers"
).toDF()

silver_suppliers_df = raw_suppliers_df \
    .withColumn("supplier_id", F.trim(F.col("supplier_id"))) \
    .withColumn("supplier_name", F.trim(F.col("supplier_name"))) \
    .withColumn("lead_time_days", F.col("lead_time_days").cast(IntegerType())) \
    .withColumn("minimum_order_quantity", F.col("minimum_order_quantity").cast(IntegerType())) \
    .withColumn("reorder_multiple", F.col("reorder_multiple").cast(IntegerType())) \
    .filter(F.col("supplier_id").isNotNull()) \
    .dropDuplicates(["supplier_id"])

silver_suppliers_df.write \
    .mode("overwrite") \
    .parquet(f"s3://{s3_bucket}/silver/suppliers/")

job.commit()