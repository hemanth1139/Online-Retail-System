#!/usr/bin/env python3

import os
import uuid
import logging
from datetime import datetime, timezone

import boto3
import awswrangler as wr
import numpy as np
import pandas as pd

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


# =========================================================
# CONFIGURATION
# =========================================================

BUCKET = "online-retail-inventory-project"
GOLD_DATABASE = "retail_gold"
FEATURE_TABLE = "product_demand_features"

# Must match the AWS region containing your Athena/S3 resources.
AWS_REGION = os.environ.get(
    "AWS_DEFAULT_REGION",
    os.environ.get("AWS_REGION", "ap-southeast-2")
)

# Use one explicit session for all AWS services.
BOTO3_SESSION = boto3.Session(region_name=AWS_REGION)

ATHENA_OUTPUT = f"s3://{BUCKET}/athena_temp/"

FORECAST_HORIZON = 30
TEST_DAYS = 7

MODEL_VERSION = "xgboost_demand_v1"
RUN_ID = str(uuid.uuid4())
GENERATED_AT = datetime.now(timezone.utc).replace(tzinfo=None)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEATURES = [
    "sales_lag_1",
    "sales_lag_7",
    "sales_lag_14",
    "sales_lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "rolling_std_7",
    "day_of_week",
    "month",
    "day_of_month",
    "is_weekend"
]


# =========================================================
# 1. READ GOLD FEATURES FROM ATHENA
# =========================================================

def read_gold_features():

    query = f"""
        SELECT
            product_id,
            transaction_date,
            units_sold,
            sales_lag_1,
            sales_lag_7,
            sales_lag_14,
            sales_lag_28,
            rolling_mean_7,
            rolling_mean_28,
            rolling_std_7,
            day_of_week,
            month,
            day_of_month,
            is_weekend
        FROM "{GOLD_DATABASE}"."{FEATURE_TABLE}"
    """

    logger.info("Connecting to Athena in region: %s", AWS_REGION)

    df = wr.athena.read_sql_query(
        sql=query,
        database=GOLD_DATABASE,
        ctas_approach=False,
        s3_output=ATHENA_OUTPUT,
        boto3_session=BOTO3_SESSION
    )

    if df.empty:
        raise ValueError("No records returned from Athena.")

    required_columns = [
        "product_id",
        "transaction_date",
        "units_sold"
    ] + FEATURES

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df["product_id"] = df["product_id"].astype(str)

    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"],
        errors="coerce"
    ).dt.normalize()

    numeric_columns = ["units_sold"] + FEATURES

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "product_id",
            "transaction_date",
            "units_sold"
        ]
    )

    df[FEATURES] = (
        df[FEATURES]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )

    df["units_sold"] = df["units_sold"].clip(lower=0)

    df = df.sort_values(
        ["product_id", "transaction_date"]
    ).reset_index(drop=True)

    if df.empty:
        raise ValueError("No usable Gold demand features found.")

    logger.info("Historical rows loaded: %s", len(df))
    logger.info("Products found: %s", df["product_id"].nunique())

    return df


# =========================================================
# 2. BUILD XGBOOST MODEL
# =========================================================

def build_model():

    return XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1
    )


# =========================================================
# 3. MODEL EVALUATION
# =========================================================

def evaluate_model(df):

    latest_date = df["transaction_date"].max()

    split_date = (
        latest_date - pd.Timedelta(days=TEST_DAYS - 1)
    )

    train = df[
        df["transaction_date"] < split_date
    ].copy()

    test = df[
        df["transaction_date"] >= split_date
    ].copy()

    if train.empty or test.empty:
        raise ValueError(
            "Insufficient history for chronological evaluation. "
            "Reduce TEST_DAYS or provide more historical data."
        )

    model = build_model()

    model.fit(
        train[FEATURES],
        train["units_sold"]
    )

    xgb_predictions = np.maximum(
        model.predict(test[FEATURES]),
        0
    )

    baseline_lag7 = np.maximum(
        test["sales_lag_7"].to_numpy(),
        0
    )

    baseline_mean7 = np.maximum(
        test["rolling_mean_7"].to_numpy(),
        0
    )

    models = {
        "XGBoost": xgb_predictions,
        "Lag_7_Baseline": baseline_lag7,
        "Rolling_Mean_7_Baseline": baseline_mean7
    }

    results = []

    for model_name, predictions in models.items():

        results.append({
            "model_name": model_name,
            "model_version": MODEL_VERSION,

            "mae": float(
                mean_absolute_error(
                    test["units_sold"],
                    predictions
                )
            ),

            "rmse": float(
                np.sqrt(
                    mean_squared_error(
                        test["units_sold"],
                        predictions
                    )
                )
            ),

            "test_start_date": split_date.date(),
            "test_end_date": latest_date.date(),
            "test_rows": int(len(test)),
            "run_id": RUN_ID,
            "generated_at": GENERATED_AT
        })

    metrics = pd.DataFrame(results)

    print("\nMODEL EVALUATION")
    print(metrics.to_string(index=False))

    return metrics


# =========================================================
# 4. FUTURE CALENDAR FEATURES
# =========================================================

def get_calendar_features(date):

    weekday = date.isoweekday()

    return {
        "day_of_week": weekday,
        "month": date.month,
        "day_of_month": date.day,
        "is_weekend": int(weekday in [6, 7])
    }


# =========================================================
# 5. RECURSIVE FUTURE FORECASTING
# =========================================================

def generate_forecasts(df, model):

    results = []

    for product_id, group in df.groupby("product_id"):

        group = group.sort_values("transaction_date")

        history = list(
            group["units_sold"].astype(float).values
        )

        last_date = group["transaction_date"].max()

        if not history:
            continue

        for day in range(1, FORECAST_HORIZON + 1):

            forecast_date = (
                last_date + pd.Timedelta(days=day)
            )

            def lag_value(n):
                if len(history) >= n:
                    return float(history[-n])
                return 0.0

            last_7 = history[-7:]
            last_28 = history[-28:]

            calendar = get_calendar_features(forecast_date)

            row = {
                "sales_lag_1": lag_value(1),
                "sales_lag_7": lag_value(7),
                "sales_lag_14": lag_value(14),
                "sales_lag_28": lag_value(28),

                "rolling_mean_7": (
                    float(np.mean(last_7))
                    if last_7 else 0.0
                ),

                "rolling_mean_28": (
                    float(np.mean(last_28))
                    if last_28 else 0.0
                ),

                "rolling_std_7": (
                    float(np.std(last_7))
                    if last_7 else 0.0
                ),

                **calendar
            }

            input_df = pd.DataFrame(
                [row],
                columns=FEATURES
            )

            predicted_units = max(
                0.0,
                float(model.predict(input_df)[0])
            )

            history.append(predicted_units)

            results.append({
                "product_id": str(product_id),
                "forecast_date": forecast_date.date(),
                "predicted_units": predicted_units,
                "model_version": MODEL_VERSION,
                "run_id": RUN_ID,
                "generated_at": GENERATED_AT
            })

    return pd.DataFrame(results)


# =========================================================
# 6. CREATE 7-DAY AND 30-DAY SUMMARY
# =========================================================

def create_forecast_summary(forecasts):

    forecasts = forecasts.sort_values(
        ["product_id", "forecast_date"]
    )

    rows = []

    for product_id, group in forecasts.groupby("product_id"):

        group = group.sort_values("forecast_date")

        rows.append({
            "product_id": product_id,

            "forecast_7d_units": float(
                group.head(7)["predicted_units"].sum()
            ),

            "forecast_30d_units": float(
                group.head(30)["predicted_units"].sum()
            ),

            "avg_daily_forecast_units": float(
                group.head(30)["predicted_units"].mean()
            ),

            "model_version": MODEL_VERSION,
            "run_id": RUN_ID,
            "generated_at": GENERATED_AT
        })

    return pd.DataFrame(rows)


# =========================================================
# 7. SAVE OUTPUTS TO S3
# =========================================================

def save_to_s3(df, path):

    wr.s3.to_parquet(
        df=df,
        path=path,
        index=False,
        dataset=False,
        boto3_session=BOTO3_SESSION
    )

    print("Saved:", path)


# =========================================================
# 8. MAIN EXECUTION
# =========================================================

def main():

    print("AWS Region:", AWS_REGION)
    print("Run ID:", RUN_ID)

    print("\nReading Gold demand features...")
    df = read_gold_features()

    print("Historical rows:", len(df))
    print("Products:", df["product_id"].nunique())

    print("\nEvaluating models...")
    metrics = evaluate_model(df)

    print("\nTraining final XGBoost model...")

    final_model = build_model()

    final_model.fit(
        df[FEATURES],
        df["units_sold"]
    )

    print("\nGenerating future forecasts...")

    forecasts = generate_forecasts(
        df,
        final_model
    )

    if forecasts.empty:
        raise ValueError("No forecasts generated.")

    summary = create_forecast_summary(forecasts)

    print("\nSaving results to S3...")

    save_to_s3(
        forecasts,
        f"s3://{BUCKET}/ml/predictions/daily_forecasts_{RUN_ID}.parquet"
    )

    save_to_s3(
        summary,
        f"s3://{BUCKET}/ml/predictions/forecast_summary_{RUN_ID}.parquet"
    )

    save_to_s3(
        metrics,
        f"s3://{BUCKET}/ml/evaluation/model_metrics_{RUN_ID}.parquet"
    )

    save_to_s3(
        forecasts,
        f"s3://{BUCKET}/ml/latest/daily_forecasts.parquet"
    )

    save_to_s3(
        summary,
        f"s3://{BUCKET}/ml/latest/forecast_summary.parquet"
    )

    save_to_s3(
        metrics,
        f"s3://{BUCKET}/ml/latest/model_metrics.parquet"
    )

    print("\nML FORECASTING COMPLETED")
    print("Run ID:", RUN_ID)
    print("Forecast rows:", len(forecasts))
    print("Products:", summary["product_id"].nunique())


if __name__ == "__main__":
    main()