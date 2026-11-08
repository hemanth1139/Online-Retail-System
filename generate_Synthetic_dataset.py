
import pandas as pd
import numpy as np
import os

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = "Online_Retail.csv"
OUTPUT_DIR = "synthetic_data"

RANDOM_SEED = 42
NUMBER_OF_SUPPLIERS = 15

np.random.seed(RANDOM_SEED)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# 1. READ AND VALIDATE ORIGINAL DATASET
# --------------------------------------------------

print("Reading Online Retail dataset...")

df = pd.read_csv(
    INPUT_FILE,
    encoding="ISO-8859-1",
    dtype={"StockCode": "string"}
)

# Remove accidental spaces from column names
df.columns = df.columns.str.strip()

required_columns = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country"
]

missing_columns = set(required_columns) - set(df.columns)

if missing_columns:
    raise ValueError(f"Missing columns: {missing_columns}")

# Convert columns to appropriate data types
df["InvoiceDate"] = pd.to_datetime(
    df["InvoiceDate"],
    errors="coerce"
)

df["StockCode"] = df["StockCode"].str.strip()

df["Invoice"] = df["Invoice"].astype("string").str.strip()

df["Quantity"] = pd.to_numeric(
    df["Quantity"],
    errors="coerce"
)

df["Price"] = pd.to_numeric(
    df["Price"],
    errors="coerce"
)

# Remove records with missing essential values
df = df.dropna(
    subset=["StockCode", "Description", "InvoiceDate",
            "Quantity", "Price", "Invoice"]
)

# --------------------------------------------------
# 2. CLEAN SALES DATA FOR SYNTHETIC DATA GENERATION
# --------------------------------------------------

# Remove cancelled invoices
df = df[
    ~df["Invoice"].str.upper().str.startswith("C", na=False)
]

# Keep only positive sales quantities and prices
sales_df = df[
    (df["Quantity"] > 0) &
    (df["Price"] > 0)
].copy()

if sales_df.empty:
    raise ValueError("No valid positive sales records found.")

print("Valid sales records:", len(sales_df))

# --------------------------------------------------
# 3. GENERATE PRODUCTS DATASET
# --------------------------------------------------

print("\nGenerating products.csv...")

products = (
    sales_df.groupby("StockCode")
    .agg(
        product_name=("Description", "first"),
        unit_price=("Price", "median")
    )
    .reset_index()
)

products.rename(
    columns={"StockCode": "product_id"},
    inplace=True
)

products["unit_price"] = products["unit_price"].round(2)

products.to_csv(
    f"{OUTPUT_DIR}/products.csv",
    index=False
)

print("Products generated:", len(products))

# --------------------------------------------------
# 4. GENERATE SUPPLIERS DATASET
# --------------------------------------------------

print("\nGenerating suppliers.csv...")

suppliers = pd.DataFrame({
    "supplier_id": [
        f"SUP{i:03d}"
        for i in range(1, NUMBER_OF_SUPPLIERS + 1)
    ],

    "supplier_name": [
        f"Supplier_{i:03d}"
        for i in range(1, NUMBER_OF_SUPPLIERS + 1)
    ],

    "lead_time_days": np.random.randint(
        2, 15, NUMBER_OF_SUPPLIERS
    ),

    "minimum_order_quantity": np.random.choice(
        [5, 10, 15, 20, 25, 50],
        NUMBER_OF_SUPPLIERS
    ),

    "reorder_multiple": np.random.choice(
        [1, 5, 10],
        NUMBER_OF_SUPPLIERS
    )
})

suppliers.to_csv(
    f"{OUTPUT_DIR}/suppliers.csv",
    index=False
)

print("Suppliers generated:", len(suppliers))

# --------------------------------------------------
# 5. CALCULATE AVERAGE DAILY PRODUCT DEMAND
# --------------------------------------------------

print("\nCalculating product demand...")

sales_df["sales_date"] = sales_df["InvoiceDate"].dt.date

daily_sales = (
    sales_df.groupby(
        ["StockCode", "sales_date"]
    )["Quantity"]
    .sum()
    .reset_index()
)

# Use the full observation period so that days
# without sales are also reflected in average demand.

total_days = (
    sales_df["InvoiceDate"].max().normalize()
    - sales_df["InvoiceDate"].min().normalize()
).days + 1

total_days = max(total_days, 1)

product_demand = (
    daily_sales.groupby("StockCode")["Quantity"]
    .sum()
    .reset_index(name="total_quantity_sold")
)

product_demand["average_daily_demand"] = (
    product_demand["total_quantity_sold"] / total_days
)

# --------------------------------------------------
# 6. GENERATE INVENTORY DATASET
# --------------------------------------------------

print("\nGenerating inventory.csv...")

inventory = products[["product_id"]].copy()

# Connect each product with a randomly assigned supplier
inventory["supplier_id"] = np.random.choice(
    suppliers["supplier_id"].values,
    size=len(inventory)
)

# Add average daily demand
inventory = inventory.merge(
    product_demand[
        ["StockCode", "average_daily_demand"]
    ],
    left_on="product_id",
    right_on="StockCode",
    how="left"
)

inventory.drop(columns=["StockCode"], inplace=True)

inventory["average_daily_demand"] = (
    inventory["average_daily_demand"].fillna(0)
)

# Add supplier lead time
inventory = inventory.merge(
    suppliers[["supplier_id", "lead_time_days"]],
    on="supplier_id",
    how="left"
)

# Generate synthetic safety stock
inventory["safety_stock"] = np.ceil(
    inventory["average_daily_demand"]
    * inventory["lead_time_days"]
    * 0.5
).astype(int)

# Generate synthetic current inventory
# Simulate between 1 and 30 days of stock coverage
stock_coverage_days = np.random.randint(
    1, 31, size=len(inventory)
)

inventory["current_stock"] = np.ceil(
    inventory["average_daily_demand"]
    * stock_coverage_days
).astype(int)

# Snapshot date is one day after the last transaction
snapshot_date = (
    sales_df["InvoiceDate"].max().normalize()
    + pd.Timedelta(days=1)
)

inventory["snapshot_date"] = snapshot_date.date()

# Select final columns
inventory = inventory[
    [
        "product_id",
        "supplier_id",
        "current_stock",
        "safety_stock",
        "snapshot_date"
    ]
]

inventory.to_csv(
    f"{OUTPUT_DIR}/inventory.csv",
    index=False
)

print("Inventory records generated:", len(inventory))

# --------------------------------------------------
# 7. FINAL VALIDATION
# --------------------------------------------------

print("\n========== VALIDATION ==========")

print("Products:", len(products))
print("Suppliers:", len(suppliers))
print("Inventory:", len(inventory))

print(
    "Missing product references:",
    (~inventory["product_id"].isin(products["product_id"])).sum()
)

print(
    "Invalid supplier references:",
    (~inventory["supplier_id"].isin(suppliers["supplier_id"])).sum()
)

print(
    "Negative stock records:",
    (inventory["current_stock"] < 0).sum()
)

print("\n========== SAMPLE OUTPUTS ==========")

print("\nProducts:")
print(products.head())

print("\nSuppliers:")
print(suppliers.head())

print("\nInventory:")
print(inventory.head())

print("\nAll three synthetic datasets generated successfully!")
print("Output folder:", OUTPUT_DIR)
