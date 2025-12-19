import pandas as pd
import mysql.connector
import os

OUTPUT_FILE = "recommender/trained_models/hybrid_training_data.csv"

def fetch_data():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="teim1"
    )
    cursor = db.cursor(dictionary=True)

    print("📥 Fetching purchase history...")
    cursor.execute("""
        SELECT 
            ph.id AS purchase_id,
            ph.customer_id,
            ph.product_id,
            ph.product_name,
            ph.quantity,
            ph.total_amount,
            ph.purchased_at,
            c.fullname,
            c.customer_type,
            c.shifttopartycity,
            c.shifttopartystate,
            pr.category,
            pr.hsn_code
        FROM crmapp_purchasehistory ph
        LEFT JOIN crmapp_customer_details c 
            ON ph.customer_id = c.customerid
        LEFT JOIN crmapp_product pr
            ON ph.product_id = pr.product_id
        WHERE ph.product_id IS NOT NULL
    """)

    purchase_data = cursor.fetchall()
    df = pd.DataFrame(purchase_data)

    print(f"📊 Loaded {len(df)} purchase records.")

    # PROCESSING
    df["quantity"] = df["quantity"].astype(float)
    df["total_amount"] = df["total_amount"].astype(float)

    # Create simple rating
    df["rating"] = df["quantity"].apply(lambda q: 5 if q > 10 else (4 if q > 5 else 3))

    # Fill missing categories
    df["category"] = df["category"].fillna("Unknown")

    print("✅ Data cleaned successfully.")

    # Export CSV
    os.makedirs("recommender/trained_models", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"📁 Training dataset saved to: {OUTPUT_FILE}")

    return df


if __name__ == "__main__":
    fetch_data()
