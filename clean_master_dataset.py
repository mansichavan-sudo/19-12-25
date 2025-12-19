import pandas as pd

print("\n🚀 Starting Cleaning Process...\n")

# --------------------------------------------
# 1️⃣ Load CSV properly (UTF-16 + TAB)
# --------------------------------------------
try:
    df = pd.read_csv("master_dataset.csv", encoding="utf-16", sep="\t")
    used_encoding = "utf-16"
except:
    df = pd.read_csv("master_dataset.csv", encoding="utf-16le", sep="\t")
    used_encoding = "utf-16le"

print(f"📌 Loaded with encoding: {used_encoding}")
print("📌 Detected Raw Columns:", list(df.columns))

# --------------------------------------------
# 2️⃣ FIX BOM in first col name
# --------------------------------------------
df.columns = [col.replace("﻿", "").strip().lower() for col in df.columns]

print("📌 Normalized Columns:", list(df.columns))

# --------------------------------------------
# 3️⃣ Required columns check
# --------------------------------------------
required = ["customer_id", "product_id", "product_name"]
missing = [c for c in required if c not in df.columns]

if missing:
    print("❌ ERROR: Missing required columns:", missing)
    exit()

# --------------------------------------------
# 4️⃣ Clean data
# --------------------------------------------
df["customer_id"] = df["customer_id"].astype(str).str.strip()
df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce")
df["product_name"] = df["product_name"].astype(str).str.strip()

# Drop invalid rows
df = df.dropna(subset=["product_id", "product_name"])

# Numeric fields
for col in ["total_quantity", "total_orders"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(1)
    else:
        df[col] = 1

# Category
if "category" in df.columns:
    df["category"] = (
        df["category"].fillna("unknown")
        .astype(str)
        .str.lower()
        .str.replace(" ", "_")
    )
else:
    df["category"] = "unknown"

# Dates
if "last_purchase" in df.columns:
    df["last_purchase"] = pd.to_datetime(
        df["last_purchase"], errors="coerce"
    ).dt.date

# Remove duplicates
df = df.drop_duplicates(
    subset=["customer_id", "product_id", "source"],
    keep="first"
)

print("✅ Cleaned rows:", len(df))

# --------------------------------------------
# 5️⃣ Save Final File
# --------------------------------------------
df.to_csv("master_dataset_cleaned.csv", index=False, encoding="utf-8")

print("🎉 Cleaning complete! File saved as master_dataset_cleaned.csv")

