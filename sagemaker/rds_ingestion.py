#!/usr/bin/env python
import sys
import subprocess

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "numpy==1.24.1", "pandas<2.0.0", "awswrangler", "psycopg2-binary", "pyarrow", "boto3"
])
import os
import boto3
import awswrangler as wr

AWS_REGION = os.environ.get(
    "AWS_DEFAULT_REGION",
    os.environ.get("AWS_REGION", "ap-southeast-2")
)
# Secrets Manager
secrets_client = BOTO3_SESSION.client("secretsmanager")

# S3
s3_client = BOTO3_SESSION.client("s3")

BOTO3_SESSION = boto3.Session(region_name=AWS_REGION)

import re
import json
import logging

import boto3
import awswrangler as wr
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# =========================================================
# CONFIGURATION
# =========================================================

BUCKET = "online-retail-inventory-project"
DB_SECRET_ARN = "retail_project_rds_credential"
DB_NAME = "postgres"
DB_SCHEMA = "retail_serving"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", DB_SCHEMA):
    raise ValueError("Invalid PostgreSQL schema name.")


# =========================================================
# 1. READ RDS CREDENTIALS FROM SECRETS MANAGER
# =========================================================

def get_db_credentials(secret_name=DB_SECRET_ARN, region_name="ap-southeast-2"):
    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


# =========================================================
# 2. CONNECT TO POSTGRESQL
# =========================================================

def connect_to_rds():
    secret = get_db_credentials()
    connection = psycopg2.connect(
        host=secret["host"],
        port=int(secret.get("port", 5432)),
        database=DB_NAME,
        user=secret["username"],
        password=secret["password"],
        connect_timeout=15,
        sslmode="require"
    )
    return connection


# =========================================================
# 3. READ PARQUET OUTPUTS FROM S3
# =========================================================

def read_s3_data(key):
    path = f"s3://{BUCKET}/{key}"
    df = wr.s3.read_parquet(path=path)
    print(f"Read {len(df)} rows from {path}")
    return df


# =========================================================
# 4. CONVERT PANDAS VALUES FOR POSTGRESQL
# =========================================================

def clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        value = value.item()
    return value


def create_records(df, columns):
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return [
        tuple(clean_value(value) for value in row)
        for row in df[columns].itertuples(index=False, name=None)
    ]


# =========================================================
# 5. CREATE POSTGRESQL TABLES
# =========================================================

def create_tables(connection):
    sql = f"""
    CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA};

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.model_metrics (
        model_name VARCHAR(100) NOT NULL,
        model_version VARCHAR(100) NOT NULL,
        run_id VARCHAR(100) NOT NULL,
        mae DOUBLE PRECISION,
        rmse DOUBLE PRECISION,
        test_start_date DATE,
        test_end_date DATE,
        test_rows BIGINT,
        generated_at TIMESTAMP,
        PRIMARY KEY (model_name, run_id)
    );

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.daily_forecasts (
        product_id VARCHAR(100) NOT NULL,
        forecast_date DATE NOT NULL,
        predicted_units DOUBLE PRECISION NOT NULL,
        model_version VARCHAR(100) NOT NULL,
        run_id VARCHAR(100) NOT NULL,
        generated_at TIMESTAMP,
        PRIMARY KEY (
            product_id,
            forecast_date,
            model_version
        )
    );

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.inventory_recommendations (
        product_id VARCHAR(100) PRIMARY KEY,
        product_name TEXT,
        unit_price DOUBLE PRECISION,
        supplier_id VARCHAR(100),
        supplier_name TEXT,
        current_stock INTEGER,
        safety_stock INTEGER,
        snapshot_date DATE,
        lead_time_days INTEGER,
        minimum_order_quantity INTEGER,
        reorder_multiple INTEGER,
        forecast_7d_units DOUBLE PRECISION,
        forecast_30d_units DOUBLE PRECISION,
        avg_daily_forecast_units DOUBLE PRECISION,
        lead_time_demand DOUBLE PRECISION,
        reorder_point DOUBLE PRECISION,
        target_stock DOUBLE PRECISION,
        raw_order_quantity INTEGER,
        recommended_order_quantity INTEGER,
        stock_status VARCHAR(30),
        recommendation_reason TEXT,
        review_period_days INTEGER,
        inventory_data_type VARCHAR(30),
        supplier_data_type VARCHAR(30),
        run_id VARCHAR(100),
        generated_at TIMESTAMP
    );
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()
    print("PostgreSQL tables created or verified.")


# =========================================================
# 6. INSERTS
# =========================================================

def insert_model_metrics(connection, df):
    columns = [
        "model_name", "model_version", "run_id", "mae", "rmse",
        "test_start_date", "test_end_date", "test_rows", "generated_at"
    ]
    records = create_records(df, columns)
    if not records:
        return

    sql = f"""
        INSERT INTO {DB_SCHEMA}.model_metrics
        ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (model_name, run_id)
        DO UPDATE SET
            model_version = EXCLUDED.model_version,
            mae = EXCLUDED.mae,
            rmse = EXCLUDED.rmse,
            test_start_date = EXCLUDED.test_start_date,
            test_end_date = EXCLUDED.test_end_date,
            test_rows = EXCLUDED.test_rows,
            generated_at = EXCLUDED.generated_at
    """

    with connection.cursor() as cursor:
        execute_values(cursor, sql, records)
    connection.commit()
    print("Model metrics inserted.")


def insert_daily_forecasts(connection, df):
    columns = [
        "product_id", "forecast_date", "predicted_units",
        "model_version", "run_id", "generated_at"
    ]
    records = create_records(df, columns)
    if not records:
        return

    sql = f"""
        INSERT INTO {DB_SCHEMA}.daily_forecasts
        ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (product_id, forecast_date, model_version)
        DO UPDATE SET
            predicted_units = EXCLUDED.predicted_units,
            run_id = EXCLUDED.run_id,
            generated_at = EXCLUDED.generated_at
    """

    with connection.cursor() as cursor:
        execute_values(cursor, sql, records, page_size=5000)
    connection.commit()
    print("Daily forecasts inserted.")


def insert_inventory_recommendations(connection, df):
    columns = [
        "product_id", "product_name", "unit_price", "supplier_id", "supplier_name",
        "current_stock", "safety_stock", "snapshot_date", "lead_time_days",
        "minimum_order_quantity", "reorder_multiple", "forecast_7d_units",
        "forecast_30d_units", "avg_daily_forecast_units", "lead_time_demand",
        "reorder_point", "target_stock", "raw_order_quantity",
        "recommended_order_quantity", "stock_status", "recommendation_reason",
        "review_period_days", "inventory_data_type", "supplier_data_type",
        "run_id", "generated_at"
    ]
    records = create_records(df, columns)
    if not records:
        return

    sql = f"""
        INSERT INTO {DB_SCHEMA}.inventory_recommendations
        ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (product_id)
        DO UPDATE SET
            product_name = EXCLUDED.product_name,
            unit_price = EXCLUDED.unit_price,
            supplier_id = EXCLUDED.supplier_id,
            supplier_name = EXCLUDED.supplier_name,
            current_stock = EXCLUDED.current_stock,
            safety_stock = EXCLUDED.safety_stock,
            snapshot_date = EXCLUDED.snapshot_date,
            lead_time_days = EXCLUDED.lead_time_days,
            minimum_order_quantity = EXCLUDED.minimum_order_quantity,
            reorder_multiple = EXCLUDED.reorder_multiple,
            forecast_7d_units = EXCLUDED.forecast_7d_units,
            forecast_30d_units = EXCLUDED.forecast_30d_units,
            avg_daily_forecast_units = EXCLUDED.avg_daily_forecast_units,
            lead_time_demand = EXCLUDED.lead_time_demand,
            reorder_point = EXCLUDED.reorder_point,
            target_stock = EXCLUDED.target_stock,
            raw_order_quantity = EXCLUDED.raw_order_quantity,
            recommended_order_quantity = EXCLUDED.recommended_order_quantity,
            stock_status = EXCLUDED.stock_status,
            recommendation_reason = EXCLUDED.recommendation_reason,
            review_period_days = EXCLUDED.review_period_days,
            inventory_data_type = EXCLUDED.inventory_data_type,
            supplier_data_type = EXCLUDED.supplier_data_type,
            run_id = EXCLUDED.run_id,
            generated_at = EXCLUDED.generated_at
    """

    with connection.cursor() as cursor:
        execute_values(cursor, sql, records, page_size=5000)
    connection.commit()
    print("Inventory recommendations inserted.")


# =========================================================
# 7. MAIN EXECUTION
# =========================================================

def main():
    print("Reading ML and inventory results from S3...")
    metrics = read_s3_data("ml/latest/model_metrics.parquet")
    forecasts = read_s3_data("ml/latest/daily_forecasts.parquet")
    recommendations = read_s3_data("ml/latest/inventory_recommendations.parquet")

    print("Connecting to PostgreSQL...")
    connection = connect_to_rds()

    try:
        create_tables(connection)
        insert_model_metrics(connection, metrics)
        insert_daily_forecasts(connection, forecasts)
        insert_inventory_recommendations(connection, recommendations)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print("\nRDS INGESTION COMPLETED")
    print("Metrics rows:", len(metrics))
    print("Forecast rows:", len(forecasts))
    print("Inventory recommendation rows:", len(recommendations))


if __name__ == "__main__":
    main()