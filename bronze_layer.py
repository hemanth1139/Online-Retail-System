
import sys

from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "S3_BUCKET_NAME", "RAW_DATABASE"]
)

BUCKET = args["S3_BUCKET_NAME"]
RAW_DATABASE = args["RAW_DATABASE"]

RAW_ONLINE_RETAIL = (
    f"s3://{BUCKET}/raw/online_retail/Online_Retail.csv"
)
BRONZE_PATH = f"s3://{BUCKET}/bronze/"

# --------------------------------------------------
# INITIALIZE
# --------------------------------------------------

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Read source CSV fields as strings so malformed numeric
# values do not abort ingestion.
online_schema = StructType([
    StructField("Invoice", StringType(), True),
    StructField("StockCode", StringType(), True),
    StructField("Description", StringType(), True),
    StructField("Quantity", StringType(), True),
    StructField("InvoiceDate", StringType(), True),
    StructField("Price", StringType(), True),
    StructField("Customer ID", StringType(), True),
    StructField("Country", StringType(), True),
    StructField("_corrupt_record", StringType(), True)
])

def add_metadata(df):
    return (
        df
        .withColumn("ingestion_timestamp", F.current_timestamp())
        .withColumn("source_file", F.input_file_name())
    )

def write_bronze(df, table_name):
    target = f"{BRONZE_PATH}{table_name}/"

    (
        add_metadata(df)
        .write
        .mode("overwrite")
        .format("parquet")
        .save(target)
    )

    print(f"Written Bronze table: {table_name} -> {target}")

# --------------------------------------------------
# 1. ONLINE RETAIL
# --------------------------------------------------

print("Reading raw Online Retail CSV")

online_df = (
    spark.read
    .format("csv")
    .option("header", "true")
    .option("encoding", "ISO-8859-1")
    .option("quote", '"')
    .option("escape", '"')
    .option("mode", "PERMISSIVE")
    .option("columnNameOfCorruptRecord", "_corrupt_record")
    .schema(online_schema)
    .load(RAW_ONLINE_RETAIL)
)

write_bronze(online_df, "online_retail")

# --------------------------------------------------
# 2. PRODUCTS, SUPPLIERS, INVENTORY
# --------------------------------------------------

for table_name in ["products", "suppliers", "inventory"]:

    print(f"Reading raw Catalog table: {table_name}")

    source_dyf = glueContext.create_dynamic_frame.from_catalog(
        database=RAW_DATABASE,
        table_name=table_name,
        transformation_ctx=f"source_{table_name}"
    )

    source_df = source_dyf.toDF()
    write_bronze(source_df, table_name)

# --------------------------------------------------
# 3. VALIDATE OUTPUTS
# --------------------------------------------------

for table_name in [
    "online_retail",
    "products",
    "suppliers",
    "inventory"
]:
    df = spark.read.parquet(f"{BRONZE_PATH}{table_name}/")
    print(f"{table_name}: {df.count()} rows")
    df.printSchema()

job.commit()
print("Bronze ETL completed.")
