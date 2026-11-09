
import sys
from functools import reduce

from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "S3_BUCKET_NAME", "BRONZE_DATABASE"]
)

BUCKET = args["S3_BUCKET_NAME"]
BRONZE_DATABASE = args["BRONZE_DATABASE"]

BRONZE_PATH = f"s3://{BUCKET}/bronze/"
SILVER_PATH = f"s3://{BUCKET}/silver/"


# --------------------------------------------------
# 2. INITIALIZE GLUE AND SPARK
# --------------------------------------------------

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)


# --------------------------------------------------
# 3. READ AND WRITE FUNCTIONS
# --------------------------------------------------

def read_bronze(table_name):

    dyf = glueContext.create_dynamic_frame.from_catalog(
        database=BRONZE_DATABASE,
        table_name=table_name,
        transformation_ctx=f"bronze_{table_name}"
    )

    return dyf.toDF()


def write_silver(df, table_name, partition_column=None):

    writer = (
        df.write
        .mode("overwrite")
        .format("parquet")
    )

    if partition_column:
        writer = writer.partitionBy(partition_column)

    writer.save(f"{SILVER_PATH}{table_name}/")

    print(f"Silver output written: {table_name}")


# --------------------------------------------------
# 4. ONLINE RETAIL TRANSACTIONS
# --------------------------------------------------

raw = read_bronze("online_retail")

# Normalize source values and parse timestamps safely.

transactions = (
    raw

    .withColumn("Invoice", F.trim(F.col("Invoice").cast("string")))
    .withColumn("StockCode", F.trim(F.col("StockCode").cast("string")))
    .withColumn("Description", F.trim(F.col("Description")))
    .withColumn("Country", F.trim(F.col("Country")))

    .withColumn(
        "Quantity",
        F.expr("try_cast(Quantity AS INT)")
    )

    .withColumn(
        "Price",
        F.expr("try_cast(Price AS DOUBLE)")
    )

    .withColumn(
        "customer_id",
        F.expr("try_cast(`Customer ID` AS BIGINT)")
    )

    # Safely parse multiple timestamp formats.
    .withColumn(
        "transaction_timestamp",
        F.coalesce(
            F.expr(
                "try_to_timestamp(CAST(InvoiceDate AS STRING), 'M/d/yyyy H:mm:ss')"
            ),
            F.expr(
                "try_to_timestamp(CAST(InvoiceDate AS STRING), 'M/d/yyyy H:mm')"
            ),
            F.expr(
                "try_to_timestamp(CAST(InvoiceDate AS STRING), 'yyyy-MM-dd HH:mm:ss')"
            ),
            F.expr(
                "try_to_timestamp(CAST(InvoiceDate AS STRING), 'yyyy-MM-dd HH:mm')"
            )
        )
    )

    .withColumn(
        "transaction_date",
        F.to_date("transaction_timestamp")
    )
)


# --------------------------------------------------
# 5. VALIDATION AND REJECTION REASONS
# --------------------------------------------------

invalid_checks = [
    F.col("Invoice").isNull() | (F.col("Invoice") == ""),

    F.col("StockCode").isNull() | (F.col("StockCode") == ""),

    F.col("Quantity").isNull(),

    F.col("Quantity") == 0,

    F.col("Price").isNull(),

    F.col("Price") < 0,

    F.col("transaction_timestamp").isNull(),

    F.col("Country").isNull() | (F.col("Country") == "")
]

rejection_reasons = [
    F.when(
        F.col("Invoice").isNull() | (F.col("Invoice") == ""),
        F.lit("Missing invoice")
    ),

    F.when(
        F.col("StockCode").isNull() | (F.col("StockCode") == ""),
        F.lit("Missing stock code")
    ),

    F.when(
        F.col("Quantity").isNull(),
        F.lit("Invalid quantity")
    ),

    F.when(
        F.col("Quantity") == 0,
        F.lit("Zero quantity")
    ),

    F.when(
        F.col("Price").isNull(),
        F.lit("Invalid or missing price")
    ),

    F.when(
        F.col("Price") < 0,
        F.lit("Negative price")
    ),

    F.when(
        F.col("transaction_timestamp").isNull(),
        F.lit("Invalid invoice date")
    ),

    F.when(
        F.col("Country").isNull() | (F.col("Country") == ""),
        F.lit("Missing country")
    )
]

# Check whether corrupt record column exists.

if "_corrupt_record" in transactions.columns:

    invalid_checks.append(
        F.col("_corrupt_record").isNotNull()
    )

    rejection_reasons.append(
        F.when(
            F.col("_corrupt_record").isNotNull(),
            F.lit("Malformed CSV record")
        )
    )


invalid_condition = reduce(
    lambda a, b: a | b,
    invalid_checks
)


# Create rejected records.

rejected = (
    transactions
    .filter(invalid_condition)
    .withColumn(
        "rejection_reason",
        F.concat_ws("; ", *rejection_reasons)
    )
)


# Remove unnecessary original source columns.

source_columns_to_drop = [
    "Customer ID",
    "InvoiceDate",
    "_corrupt_record"
]

rejected_cleaned = rejected.drop(*source_columns_to_drop)

write_silver(rejected_cleaned, "rejected")


# Keep only valid transactions.

valid = transactions.filter(~invalid_condition)


# --------------------------------------------------
# 6. SPLIT SALES, RETURNS AND CANCELLATIONS
# --------------------------------------------------

is_cancellation = F.upper(F.col("Invoice")).startswith("C")


# Cancellations

cancellations = (
    valid
    .filter(is_cancellation)
    .withColumn(
        "record_type",
        F.lit("CANCELLATION")
    )
)


# Returns

returns = (
    valid
    .filter(
        ~is_cancellation &
        (F.col("Quantity") < 0)
    )
    .withColumn(
        "record_type",
        F.lit("RETURN")
    )
)


# Sales

sales = (
    valid
    .filter(
        ~is_cancellation &
        (F.col("Quantity") > 0)
    )
    .withColumn(
        "record_type",
        F.lit("SALE")
    )
)


# Write curated transaction tables.

for name, df in [
    ("sales", sales),
    ("returns", returns),
    ("cancellations", cancellations)
]:

    cleaned = df.drop(*source_columns_to_drop)

    write_silver(
        cleaned,
        name,
        partition_column="transaction_date"
    )


# --------------------------------------------------
# 7. PRODUCTS
# --------------------------------------------------

products = read_bronze("products")

products = (
    products

    .withColumn(
        "product_id",
        F.trim(F.col("product_id").cast("string"))
    )

    .withColumn(
        "product_name",
        F.trim(F.col("product_name"))
    )

    .withColumn(
        "unit_price",
        F.expr("try_cast(unit_price AS DOUBLE)")
    )

    .filter(
        F.col("product_id").isNotNull()
        & (F.col("product_id") != "")
        & F.col("unit_price").isNotNull()
        & (F.col("unit_price") >= 0)
    )

    .dropDuplicates(["product_id"])
)

write_silver(products, "products")


# --------------------------------------------------
# 8. SUPPLIERS
# --------------------------------------------------

suppliers = read_bronze("suppliers")

suppliers = (
    suppliers

    .withColumn(
        "supplier_id",
        F.trim(F.col("supplier_id").cast("string"))
    )

    .withColumn(
        "supplier_name",
        F.trim(F.col("supplier_name"))
    )

    .withColumn(
        "lead_time_days",
        F.expr("try_cast(lead_time_days AS INT)")
    )

    .withColumn(
        "minimum_order_quantity",
        F.expr("try_cast(minimum_order_quantity AS INT)")
    )

    .withColumn(
        "reorder_multiple",
        F.expr("try_cast(reorder_multiple AS INT)")
    )

    .filter(
        F.col("supplier_id").isNotNull()
        & (F.col("supplier_id") != "")

        & F.col("lead_time_days").isNotNull()
        & (F.col("lead_time_days") > 0)

        & F.col("minimum_order_quantity").isNotNull()
        & (F.col("minimum_order_quantity") > 0)

        & F.col("reorder_multiple").isNotNull()
        & (F.col("reorder_multiple") > 0)
    )

    .dropDuplicates(["supplier_id"])
)

write_silver(suppliers, "suppliers")


# --------------------------------------------------
# 9. INVENTORY
# --------------------------------------------------

inventory = read_bronze("inventory")

inventory = (
    inventory

    .withColumn(
        "product_id",
        F.trim(F.col("product_id").cast("string"))
    )

    .withColumn(
        "supplier_id",
        F.trim(F.col("supplier_id").cast("string"))
    )

    .withColumn(
        "current_stock",
        F.expr("try_cast(current_stock AS INT)")
    )

    .withColumn(
        "safety_stock",
        F.expr("try_cast(safety_stock AS INT)")
    )

    .withColumn(
        "snapshot_date",
        F.to_date("snapshot_date")
    )

    .filter(
        F.col("product_id").isNotNull()
        & (F.col("product_id") != "")

        & F.col("supplier_id").isNotNull()
        & (F.col("supplier_id") != "")

        & F.col("current_stock").isNotNull()
        & (F.col("current_stock") >= 0)

        & F.col("safety_stock").isNotNull()
        & (F.col("safety_stock") >= 0)

        & F.col("snapshot_date").isNotNull()
    )
)


# Keep the latest inventory snapshot for each product.

inventory_window = (
    Window
    .partitionBy("product_id")
    .orderBy(F.col("snapshot_date").desc())
)

inventory = (
    inventory
    .withColumn(
        "_row_number",
        F.row_number().over(inventory_window)
    )
    .filter(F.col("_row_number") == 1)
    .drop("_row_number")
)

write_silver(inventory, "inventory")


# --------------------------------------------------
# 10. VALIDATION
# --------------------------------------------------

print("Starting Silver layer validation...")

for table_name in [
    "sales",
    "returns",
    "cancellations",
    "rejected",
    "products",
    "suppliers",
    "inventory"
]:

    df = spark.read.parquet(
        f"{SILVER_PATH}{table_name}/"
    )

    print(
        f"Silver table: {table_name} | Rows: {df.count()}"
    )


# --------------------------------------------------
# 11. COMMIT GLUE JOB
# --------------------------------------------------

job.commit()

print("Silver ETL completed successfully.")
