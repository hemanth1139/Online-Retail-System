# Smart Retail Demand Forecasting & Inventory Intelligence with GenAI Copilot

> An end-to-end AWS project: raw retail data → medallion data lake → XGBoost demand forecast → reorder recommendations → PostgreSQL → a terminal **GenAI Copilot** that answers plain-English questions using text-to-SQL.

---

## 1. What this project does

1. Ingests retail sales, inventory and supplier files into **Amazon S3**.
2. Cleans and transforms them with **AWS Glue (PySpark)** into **Bronze → Silver → Gold** layers.
3. Trains an **XGBoost** model to forecast the next **30 days** of demand per product.
4. Combines forecasts with stock and supplier data to calculate **reorder recommendations**.
5. Loads results into **Amazon RDS (PostgreSQL)**.
6. A **terminal Copilot** (Amazon Bedrock + Amazon Nova Lite) turns questions like *"Which products need reordering next week?"* into safe, read-only SQL and explains the result in plain English.

**Main focus:** AWS data engineering. **Also covers:** ML forecasting, inventory logic, SQL serving layer, GenAI.

---

## 2. Architecture

![Smart Retail AWS Architecture](smart_retail_aws_architecture.svg)

The project has two parts:

- **Batch pipeline (Stages 1–3):** runs automatically when new data lands in S3.
- **GenAI Copilot (Stages 4–5):** runs on demand from a terminal.

### Step-by-step flow (numbers match the diagram)

| # | Step | What happens |
|---|---|---|
| 1 | **S3 (raw)** | Source CSVs are uploaded to `raw/online_retail`, `raw/inventory`, `raw/suppliers` |
| 2 | **EventBridge** | An *S3 Object Created* rule detects the upload |
| 3 | **Step Functions** | Starts the workflow: crawlers → Glue jobs → SageMaker jobs (with retries) |
| 4 | **Bronze ETL** | Reads raw data, adds ingestion timestamp + source file, writes Parquet |
| 5 | **Silver ETL** | Cleans data, separates sales / returns / cancellations / rejected rows |
| 6 | **Gold ETL** | Builds daily sales and ML features (lags, rolling stats, calendar) |
| 7 | **Demand Forecasting** | XGBoost trains, evaluates (MAE/RMSE) and predicts 30 days |
| 8 | **Inventory Recommendations** | Calculates reorder point and order quantity |
| 9 | **RDS Ingestion** | Reads outputs from S3, gets DB password from Secrets Manager |
| 10 | **Amazon RDS** | Stores 3 serving tables in schema `retail_serving` |
| 11 | **Copilot CLI** | User types a question in the terminal |
| 12 | **Bedrock (Nova Lite)** | Builds SQL from schema + examples + question |
| 13 | **SQLGlot guard** | Checks the SQL before it touches the database |
| 14 | **Read-only query** | Safe `SELECT` runs on RDS |
| 15 | **Bedrock (Nova Lite)** | Summarises the result rows in plain English |
| 16 | **Copilot CLI** | Shows the answer, the SQL and a result table |

---

## 3. Tech stack — what I used and how

| Area | Tool | How it is used |
|---|---|---|
| Storage | **Amazon S3** | Data lake (raw/Bronze/Silver/Gold) + model outputs |
| Trigger | **Amazon EventBridge** | Starts the pipeline on S3 upload |
| Orchestration | **AWS Step Functions** | Runs crawlers, Glue jobs and SageMaker jobs in order, waits for each, retries on failure |
| Metadata | **Glue Crawlers + Data Catalog** | Discover schemas and register tables for every layer |
| ETL | **AWS Glue + PySpark** | Bronze, Silver and Gold transformations |
| ML jobs | **SageMaker Processing** | Runs forecasting, recommendation and DB-loading scripts as batch jobs (no always-on endpoint) |
| ML model | **XGBoost** | Demand forecasting |
| Database | **Amazon RDS for PostgreSQL** | Serving tables for SQL queries |
| Secrets | **AWS Secrets Manager** | Stores DB credentials (nothing hard-coded) |
| GenAI | **Amazon Bedrock (Amazon Nova Lite)** | Text-to-SQL and plain-English summaries |
| SQL safety | **SQLGlot** | Validates generated SQL before execution |
| Python libs | **Boto3, AWS Data Wrangler, PyArrow, psycopg2** | AWS access, Parquet I/O, PostgreSQL loading |
| Formats | **Parquet** | Efficient storage between layers |

---

## 4. Data

| Data | Source | Notes |
|---|---|---|
| Sales transactions | [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) | ~541,909 rows, Dec 2010 – Dec 2011, one UK online retailer |
| Inventory snapshots | Simulated | stock, safety stock, MOQ, reorder multiple |
| Supplier data | Simulated | supplier ID, lead time in days |

> ⚠️ Inventory and supplier values are **simulated** (the sales dataset has no stock data), so recommendations demonstrate the logic and are not real purchasing advice.

---

## 5. Medallion data lake (Bronze → Silver → Gold)

| Layer | Script | What it does |
|---|---|---|
| **Raw** | – | Original files, untouched |
| **Bronze** | `bronze_etl.py` | Reads CSV + catalog tables, adds ingestion metadata, writes Parquet |
| **Silver** | `siler_etl.py` | Casts types, splits sales / returns / cancellations, keeps rejected rows with reasons, keeps latest inventory snapshot |
| **Gold** | `gold_etl.py` | Creates `daily_product_sales_gold`, `inventory_analytics_gold`, `product_demand_features_gold` |

**Key cleaning rules**
- Invoice starting with `C` → cancellation (not counted as demand)
- Negative quantity → return (tracked separately)
- Missing product ID → rejected
- Rejected rows are **kept with a reason** for debugging

---

## 6. Demand forecasting (XGBoost)

**Script:** `ml_demand_forecasting.py`

**Features:** lag demand (1, 7, 14, 28 days), rolling mean (7, 28 days), rolling std (7 days), day of week, month, weekend flag.
All lags/rolling values use **only past data** to avoid data leakage.

**Process:** read Gold features → chronological train/test split → train XGBoost → compare with baselines → forecast 30 days → save to S3.

### Results (test period: 10 Nov – 9 Dec 2011, 147,480 rows, model `xgboost_demand_v1`)

| Model | MAE | RMSE |
|---|---:|---:|
| **XGBoost** | **5.9136** | **214.9434** |
| Lag-7 baseline | 6.6382 | 218.4303 |
| Rolling-mean-7 baseline | 6.1428 | 215.4107 |

- MAE is **~10.9% lower** than Lag-7 and **~3.7% lower** than Rolling-mean-7.
- RMSE is much larger than MAE → a few high-volume products have very large errors (worth investigating).
- These results apply to this test period only.

---

## 7. Inventory recommendations

**Script:** `inventory_recommendations.py` (rule-based, not ML)

```
Lead-time demand = sum of forecast demand over the supplier lead time
Reorder point    = lead-time demand + safety stock
Order quantity   = target stock − current stock (minimum 0),
                   then rounded to MOQ and reorder multiple
Status           = REORDER or SUFFICIENT (with a reason)
```

**Example:** 10 units/day × 5 days = 50, + 15 safety stock = **65**. Current stock is 40 → **REORDER**.

---

## 8. Serving database (PostgreSQL)

**Script:** `rds_ingestion.py` — loads S3 Parquet outputs into schema `retail_serving` (SSL connection via `psycopg2`, credentials from Secrets Manager).

| Table | Contents |
|---|---|
| `model_metrics` | MAE, RMSE, model version |
| `daily_forecasts` | Predicted units per product per day |
| `inventory_recommendations` | REORDER / SUFFICIENT + order quantity |

---

## 9. GenAI Copilot (text-to-SQL in the terminal)

A Python CLI where you ask questions in plain English.

**How it works**
1. You type a question.
2. The CLI builds a prompt: **table schema + few-shot SQL examples + your question**.
3. **Amazon Nova Lite on Amazon Bedrock** (called with Boto3, IAM-authenticated) returns candidate SQL.
4. The **SQLGlot guard** validates it (see below).
5. The SQL runs on RDS using a **read-only database role**.
6. Nova Lite gets the question + result rows and writes a **plain-English summary**.
7. The terminal prints the **answer, the SQL and the result table**.

**Safety — two layers**

| Layer | Protection |
|---|---|
| SQLGlot guard (in code) | `SELECT` only · only `daily_forecasts` and `inventory_recommendations` allowed · a `LIMIT` row cap is added |
| Database permissions | Read-only role with `SELECT` on those two tables only |

AI-generated SQL is never trusted blindly: even if the model produces something unexpected, the guard and the DB permissions stop it from changing data.

**Example (illustrative)**
```
copilot> Which products need reordering next week?
[SQL]    SELECT ... FROM inventory_recommendations WHERE ... = 'REORDER' LIMIT ...;
[Answer] plain-English explanation of the rows
[Table]  result rows printed in the terminal
```

---

## 10. Setup checklist

This repo contains the source code; AWS resources must be created separately.

- S3 bucket with `raw/` prefixes for sales, inventory and suppliers
- Glue crawlers, databases and the three Glue ETL jobs
- Step Functions state machine (job names and script paths must match the real files)
- EventBridge rule for *S3 Object Created*
- SageMaker Processing role
- RDS PostgreSQL instance + Secrets Manager secret for credentials
- A **read-only** database user for the Copilot
- Amazon Bedrock model access enabled in your region
- IAM roles with least-privilege permissions

```bash
python -m pip install -r requirements.txt
```

> Never commit AWS keys, passwords or secret values to GitHub.

---

## 11. Security & cost notes

- Keep S3 private and enable Block Public Access.
- Use least-privilege IAM roles; store DB credentials in Secrets Manager.
- Restrict RDS network access to the required security group.
- Stop or delete RDS and other resources when not in use; set an AWS Budget alert.
- Parquet + batch jobs keep compute cost low (no always-on ML endpoint).

---

## 12. Limitations

- Sales data is **historical** and from a single retailer.
- Inventory and supplier data are **simulated**.
- No stock-out prediction model (no real stock-out labels).
- The ML pipeline is **batch**; the Copilot only reads the latest stored results.
- The Copilot can query only two tables, and AI-generated SQL can still be *wrong* (the guard makes it safe, not necessarily correct) — answers should be checked.
- Sparse or intermittent products are hard to forecast.

---

## 13. Future improvements

- Web/API front end for the Copilot (e.g. FastAPI) and a dashboard
- Real inventory and supplier feeds
- WAPE and forecast bias metrics; confidence intervals
- Model versioning and scheduled retraining
- CloudWatch alarms and failure notifications
- Copilot query logging and automated tests / CI-CD

---

## 14. Skills demonstrated

- **Cloud data engineering:** S3, Glue, PySpark, Step Functions, EventBridge, Data Catalog
- **Data modelling:** medallion (Bronze/Silver/Gold) architecture, Parquet
- **Machine learning:** time-series feature engineering, XGBoost, baseline comparison, leakage prevention
- **Business logic:** reorder point, MOQ and lead-time calculations
- **Databases:** PostgreSQL on RDS, schema design, secure loading
- **GenAI:** Amazon Bedrock, prompt design, text-to-SQL, SQL validation and read-only access
- **Security:** IAM, Secrets Manager, least privilege
