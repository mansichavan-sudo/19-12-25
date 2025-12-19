import mysql.connector
import pandas as pd
import os

# ------------------------------------------
# 1. CONNECT TO MYSQL
# ------------------------------------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="teim1"
)

cursor = db.cursor(dictionary=True)

# ------------------------------------------
# 2. SQL QUERY (validated earlier)
# ------------------------------------------
QUERY = """
SELECT
    ph.customer_id,
    ph.product_name,

    SUM(ph.quantity) AS total_quantity,
    SUM(ph.total_amount) AS total_spend,

    COUNT(DISTINCT ph.tax_invoice_id) AS invoice_count,
    COUNT(*) AS purchase_frequency,

    MAX(ph.purchased_at) AS last_purchase_date,
    DATEDIFF(CURRENT_DATE, MAX(ph.purchased_at)) AS recency_days

FROM crmapp_purchasehistory ph
GROUP BY ph.customer_id, ph.product_name
ORDER BY ph.customer_id, ph.product_name;
"""

cursor.execute(QUERY)
rows = cursor.fetchall()

# ------------------------------------------
# 3. CONVERT TO PANDAS
# ------------------------------------------
df = pd.DataFrame(rows)

# ------------------------------------------
# 4. SAVE CSV TO recommender/data/
# ------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Create folder if not exists
os.makedirs(DATA_DIR, exist_ok=True)

output_path = os.path.join(DATA_DIR, "final_ml_training.csv")

df.to_csv(output_path, index=False)

print("✔ CSV CREATED SUCCESSFULLY!")
print("File:", output_path)
print("Total rows:", len(df))
