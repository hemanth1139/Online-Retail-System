#!/usr/bin/env python
import sys
import subprocess

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "numpy==1.24.1", "pandas<2.0.0", "awswrangler", "pyarrow"
])
import os
import boto3
import awswrangler as wr

AWS_REGION = os.environ.get(
    "AWS_DEFAULT_REGION",
    os.environ.get("AWS_REGION", "ap-southeast-2")
)

BOTO3_SESSION = boto3.Session(region_name=AWS_REGION)

import uuid
from datetime import datetime, timezone

import awswrangler as wr
import numpy as np
import pandas as pd

# =========================================================
# CONFIGURATION
# =========================================================

BUCKET = "online-retail-inventory-project"

GOLD_DATABASE = "retail_gold"
INVENTORY_TABLE = "inventory_analytics"

REVIEW_PERIOD_DAYS = 7

RUN_ID = str(uuid.uuid4())
GENERATED_AT = datetime.now(timezone.utc).replace(tzinfo=None)

# =========================================================
# 1. READ FORECAST SUMMARY FROM S3
# =========================================================

def read_forecasts():
    path = f"s3://{BUCKET}/ml/latest/forecast_summary.parquet"
    # Reading forecast Parquet from S3
    df = wr.s3.read_parquet(
    path=sys.path,
    boto3_session=BOTO3_SESSION
)

    if df.empty:
        raise ValueError("Forecast summary is empty.")

    return df


# =========================================================
# 2. READ INVENTORY ANALYTICS FROM ATHENA
# =========================================================

def read_inventory():
    query = f"""
        SELECT
            product_id,
            product_name,
            unit_price,
            supplier_id,
            supplier_name,
            current_stock,
            safety_stock,
            snapshot_date,
            lead_time_days,
            minimum_order_quantity,
            reorder_multiple
        FROM "{GOLD_DATABASE}"."{INVENTORY_TABLE}"
    """

    # Reading inventory data from Athena
    df = wr.athena.read_sql_query(
    sql=query,
    database=GOLD_DATABASE,
    ctas_approach=False,
    s3_output=f"s3://{BUCKET}/athena_temp/",
    boto3_session=BOTO3_SESSION
)

    if df.empty:
        raise ValueError("Inventory analytics table is empty.")

    return df


# =========================================================
# 3. ORDER QUANTITY ROUNDING
# =========================================================

def round_to_multiple(quantity, multiple):
    if multiple <= 0:
        raise ValueError("Reorder multiple must be greater than zero.")
    if quantity <= 0:
        return 0

    return int(
        np.ceil(quantity / multiple) * multiple
    )


def calculate_order_quantity(
    raw_quantity,
    minimum_order_quantity,
    reorder_multiple
):
    if raw_quantity <= 0:
        return 0

    rounded_quantity = round_to_multiple(
        raw_quantity,
        reorder_multiple
    )

    minimum_valid_quantity = round_to_multiple(
        minimum_order_quantity,
        reorder_multiple
    )

    return max(
        rounded_quantity,
        minimum_valid_quantity
    )


# =========================================================
# 4. MAIN RECOMMENDATION LOGIC
# =========================================================

def generate_recommendations():
    print("Reading forecast summary...")
    forecast = read_forecasts()

    print("Reading Gold inventory analytics...")
    inventory = read_inventory()

    forecast["product_id"] = forecast["product_id"].astype(str)
    inventory["product_id"] = inventory["product_id"].astype(str)

    forecast_required = [
        "product_id",
        "forecast_7d_units",
        "forecast_30d_units",
        "avg_daily_forecast_units"
    ]

    inventory_required = [
        "product_id",
        "supplier_id",
        "current_stock",
        "safety_stock",
        "lead_time_days",
        "minimum_order_quantity",
        "reorder_multiple"
    ]

    for col in forecast_required:
        if col not in forecast.columns:
            raise ValueError(f"Forecast column missing: {col}")

    for col in inventory_required:
        if col not in inventory.columns:
            raise ValueError(f"Inventory column missing: {col}")

    if inventory["product_id"].duplicated().any():
        raise ValueError("Duplicate inventory records found for a product.")

    forecast_numeric = [
        "forecast_7d_units",
        "forecast_30d_units",
        "avg_daily_forecast_units"
    ]

    inventory_numeric = [
        "current_stock",
        "safety_stock",
        "lead_time_days",
        "minimum_order_quantity",
        "reorder_multiple"
    ]

    for col in forecast_numeric + inventory_numeric:
        if col in forecast.columns:
            forecast[col] = pd.to_numeric(forecast[col], errors="coerce")
        if col in inventory.columns:
            inventory[col] = pd.to_numeric(inventory[col], errors="coerce")

    result = inventory.merge(
        forecast,
        on="product_id",
        how="left",
        validate="one_to_one",
        indicator=True
    )

    missing_forecasts = result[result["_merge"] == "left_only"]

    if not missing_forecasts.empty:
        missing_ids = missing_forecasts["product_id"].head(10).tolist()
        raise ValueError(
            f"{len(missing_forecasts)} inventory products have no forecast. "
            f"Example product IDs: {missing_ids}"
        )

    result = result.drop(columns=["_merge"])
    required_numeric = forecast_numeric + inventory_numeric

    if result[required_numeric].isna().any().any():
        raise ValueError("Missing or invalid numeric inventory/forecast values found.")

    if (
        (result["current_stock"] < 0).any()
        or (result["safety_stock"] < 0).any()
        or (result["lead_time_days"] <= 0).any()
        or (result["minimum_order_quantity"] <= 0).any()
        or (result["reorder_multiple"] <= 0).any()
        or (result["avg_daily_forecast_units"] < 0).any()
    ):
        raise ValueError("Invalid stock, demand or supplier settings.")

    result["lead_time_demand"] = (
        result["avg_daily_forecast_units"] * result["lead_time_days"]
    )

    result["reorder_point"] = (
        result["lead_time_demand"] + result["safety_stock"]
    )

    result["target_stock"] = (
        result["avg_daily_forecast_units"]
        * (result["lead_time_days"] + REVIEW_PERIOD_DAYS)
        + result["safety_stock"]
    )

    result["raw_order_quantity"] = np.maximum(
        0,
        np.ceil(result["target_stock"] - result["current_stock"])
    ).astype(int)

    result["recommended_order_quantity"] = result.apply(
        lambda row: calculate_order_quantity(
            int(row["raw_order_quantity"]),
            int(row["minimum_order_quantity"]),
            int(row["reorder_multiple"])
        ),
        axis=1
    )

    result["stock_status"] = np.where(
        result["current_stock"] <= result["reorder_point"],
        "REORDER",
        "SUFFICIENT"
    )

    result["recommendation_reason"] = np.where(
        result["recommended_order_quantity"] > 0,
        "Stock is below target stock level",
        "Current stock meets target stock level"
    )

    result["review_period_days"] = REVIEW_PERIOD_DAYS
    result["run_id"] = RUN_ID
    result["generated_at"] = GENERATED_AT
    result["inventory_data_type"] = "SIMULATED"
    result["supplier_data_type"] = "SIMULATED"

    output_columns = [
        "product_id",
        "product_name",
        "unit_price",
        "supplier_id",
        "supplier_name",
        "current_stock",
        "safety_stock",
        "snapshot_date",
        "lead_time_days",
        "minimum_order_quantity",
        "reorder_multiple",
        "forecast_7d_units",
        "forecast_30d_units",
        "avg_daily_forecast_units",
        "lead_time_demand",
        "reorder_point",
        "target_stock",
        "raw_order_quantity",
        "recommended_order_quantity",
        "stock_status",
        "recommendation_reason",
        "review_period_days",
        "inventory_data_type",
        "supplier_data_type",
        "run_id",
        "generated_at"
    ]

    output = result[output_columns].copy()

    # Both Parquet output calls
    # Both Parquet output calls
    wr.s3.to_parquet(
    df=output,
    path=output_path,
    index=False,
    dataset=False,
    boto3_session=BOTO3_SESSION
)

    print("\nINVENTORY RECOMMENDATIONS COMPLETED")
    print("Products evaluated:", len(output))
    print(
        "Products requiring reorder:",
        int((output["recommended_order_quantity"] > 0).sum())
    )

    print(
        output[
            [
                "product_id",
                "current_stock",
                "reorder_point",
                "recommended_order_quantity",
                "stock_status"
            ]
        ].head(10)
    )

    return output


if __name__ == "__main__":
    generate_recommendations()