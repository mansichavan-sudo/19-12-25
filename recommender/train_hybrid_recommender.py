import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import joblib

# -----------------------------
# DB CONNECTION
# -----------------------------
engine = create_engine(
    "mysql+pymysql://root:root@localhost:3306/teim1"
)

# -----------------------------
# LOAD DATA
# -----------------------------
purchase_df = pd.read_sql("""
    SELECT customer_id, category, item_type
    FROM crmapp_purchase_history_ml
    WHERE item_type='service'
      AND category IS NOT NULL
""", engine)

customer_features = pd.read_sql("""
    SELECT * FROM vw_ml_customer_features
""", engine)

service_popularity = pd.read_sql("""
    SELECT * FROM vw_ml_service_popularity
""", engine)

# -----------------------------
# INTERACTION MATRIX
# -----------------------------
interaction = (
    purchase_df
    .groupby(['customer_id', 'category'])
    .size()
    .reset_index(name='count')
)

pivot = interaction.pivot_table(
    index='customer_id',
    columns='category',
    values='count',
    fill_value=0
)

# -----------------------------
# COSINE SIMILARITY
# -----------------------------
similarity_matrix = cosine_similarity(pivot)
similarity_df = pd.DataFrame(
    similarity_matrix,
    index=pivot.index,
    columns=pivot.index
)

# -----------------------------
# NORMALIZE CUSTOMER FEATURES
# -----------------------------
scaler = MinMaxScaler()
customer_features_scaled = customer_features.copy()

customer_features_scaled[
    ['total_purchases', 'services_taken', 'products_bought', 'amc_count']
] = scaler.fit_transform(
    customer_features[
        ['total_purchases', 'services_taken', 'products_bought', 'amc_count']
    ]
)

# -----------------------------
# SAVE MODEL ARTIFACTS
# -----------------------------
joblib.dump({
    "pivot": pivot,
    "similarity": similarity_df,
    "customer_features": customer_features_scaled,
    "service_popularity": service_popularity
}, "hybrid_recommender.pkl")

print("✅ Hybrid recommender model trained & saved")
