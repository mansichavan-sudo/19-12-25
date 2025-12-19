import numpy as np
import pandas as pd
import mysql.connector
import pickle
import os
from django.conf import settings


# =====================================================
# DB FETCHING
# =====================================================
def fetch_dataset():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="teim1"
    )
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            ph.customer_id,
            ph.product_name,
            SUM(ph.quantity) AS total_qty
        FROM crmapp_purchasehistory ph
        GROUP BY ph.customer_id, ph.product_name
    """)

    rows = cursor.fetchall()
    db.close()

    if not rows:
        raise ValueError("No dataset from purchase history")

    df = pd.DataFrame(rows)
    df.rename(columns={"total_qty": "rating"}, inplace=True)

    # Normalize quantity into a rating scale 1–5
    df["rating"] = df["rating"].clip(1, 5)

    return df


# =====================================================
# SVD TRAINING (Custom — No Surprise Required)
# =====================================================
def train_svd(df, k=20, lr=0.005, reg=0.02, epochs=25):
    """
    Basic matrix factorization using gradient descent.
    df requires: customer_id, product_name, rating
    """

    # Encode IDs
    df["uid"] = df["customer_id"].astype("category").cat.codes
    df["pid"] = df["product_name"].astype("category").cat.codes

    n_users = df["uid"].nunique()
    n_items = df["pid"].nunique()

    # Mappings for prediction later
    user_map = dict(zip(df["uid"], df["customer_id"]))
    product_map = dict(zip(df["pid"], df["product_name"]))

    # Initialize Latent Matrices
    P = np.random.normal(scale=1./k, size=(n_users, k))
    Q = np.random.normal(scale=1./k, size=(n_items, k))

    # Training Loop
    for epoch in range(epochs):
        for _, row in df.iterrows():
            u = int(row["uid"])
            i = int(row["pid"])
            r = row["rating"]

            prediction = np.dot(P[u], Q[i])
            error = r - prediction

            # Gradient update
            P[u] += lr * (error * Q[i] - reg * P[u])
            Q[i] += lr * (error * P[u] - reg * Q[i])

        print(f"Epoch {epoch+1}/{epochs} completed")

    return P, Q, user_map, product_map


# =====================================================
# SAVE MODEL
# =====================================================
def save_model(model):
    model_path = os.path.join(
        settings.BASE_DIR,
        "recommender",
        "trained_models",
        "hybrid_recommender.pkl"
    )
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    print(f"✅ Hybrid SVD Model Saved at {model_path}")


# =====================================================
# MAIN TRAIN FUNCTION
# =====================================================
def train_hybrid():
    print("📥 Loading dataset from MySQL...")
    df = fetch_dataset()

    print("🔧 Training SVD model...")
    P, Q, user_map, product_map = train_svd(df)

    model = {
        "P": P,
        "Q": Q,
        "user_map": user_map,
        "product_map": product_map
    }

    save_model(model)
    print("🎉 Training completed!")

    return model
