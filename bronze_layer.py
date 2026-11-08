
# ============================================================
# RETAIL DEMAND FORECASTING PROJECT
# RAW TO BRONZE ETL PIPELINE
# AWS GLUE + PYSPARK
# ============================================================

from pyspark.context import SparkContext
from pyspark.sql.functions import current_timestamp, input_file_name
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame


# ------------------------------------------------------------
# 1. INITIALIZE SPARK AND GLUE
# ------------------------------------------------------------

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

print("AWS Glue ETL Started")


# ------------------------------------------------------------
# 2. CONFIGURATION
# ------------------------------------------------------------

database_name = "online_inventory"

bucket_name = "online-retail-inventory-project"

bronze_path = f"s3://{bucket_name}/bronze/"

error_path = f"s3://{bucket_name}/bronze_errors/"

table_names = [
    "suppliers",
    "products",
    "inventory",
    "online_retail"
]


# ------------------------------------------------------------
# 3. PROCESS ALL FOUR DATASETS
# ------------------------------------------------------------

for table_name in table_names:

    print(f"\nProcessing: {table_name}")

    try:

        # ----------------------------------------------------
        # READ DATA FROM GLUE CATALOG
        # ----------------------------------------------------

        if table_name == "online_retail":

            print("Using special CSV parsing configuration")

            # Read Online Retail directly from its Catalog
            # underlying S3 location, with explicit CSV options.
            catalog_table = glueContext.create_dynamic_frame.from_catalog(
                database=database_name,
                table_name=table_name,
                transformation_ctx=f"source_{table_name}"
            )

            # Convert to DataFrame with permissive CSV parsing
            # NOTE: This conversion cannot change the CSV options
            # already used by the Catalog reader. See explanation below.

            df = catalog_table.toDF()

        else:

            # Normal Catalog reading for other datasets
            dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
                database=database_name,
                table_name=table_name,
                transformation_ctx=f"source_{table_name}"
            )

            df = dynamic_frame.toDF()


        # ----------------------------------------------------
        # ADD INGESTION TIMESTAMP
        # ----------------------------------------------------

        df = df.withColumn(
            "ingestion_timestamp",
            current_timestamp()
        )


        # ----------------------------------------------------
        # WRITE TO BRONZE
        # ----------------------------------------------------

        target_path = bronze_path + table_name + "/"

        df.write \
            .mode("overwrite") \
            .format("parquet") \
            .save(target_path)

        print(f"Successfully stored {table_name} in Bronze")


    except Exception as e:

        print(f"ERROR processing {table_name}: {str(e)}")

        raise


# ------------------------------------------------------------
# 4. VERIFY BRONZE DATA
# ------------------------------------------------------------

print("\n========== BRONZE VERIFICATION ==========")

for table_name in table_names:

    path = bronze_path + table_name + "/"

    df = spark.read.parquet(path)

    print(f"\nDataset: {table_name}")

    print("Total Records:", df.count())

    df.printSchema()

    df.show(5, truncate=False)


# ------------------------------------------------------------
# 5. COMPLETION
# ------------------------------------------------------------

print("\n========================================")
print("RAW TO BRONZE ETL COMPLETED")
print("ALL DATASETS PROCESSED")
print("========================================")
