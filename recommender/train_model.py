import pandas as pd
import pickle
import os
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------
# PATHS
# ---------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_FILE = os.path.join(BASE_DIR, "data", "data", "final_ml_training.csv")
MODEL_DIR = os.path.join(BASE_DIR, "trained_models")
MODEL_FILE = os.path.join(MODEL_DIR, "recommender_model.pkl")

# Ensure model directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

print("➡ Loading dataset:", TRAIN_FILE)

# ---------------------------------------------------
# Load dataset
# ---------------------------------------------------
df = pd.read_csv(TRAIN_FILE)

if df.empty:
    print("❌ ERROR: final_ml_training.csv is EMPTY!")
    exit()

print("✔ Training rows:", len(df))
print("✔ Columns:", df.columns.tolist())

# ---------------------------------------------------
# Create pivot matrix (Customer × Product)
# Use total_quantity instead of quantity
# ---------------------------------------------------
pivot = df.pivot_table(
    index="customer_id",
    columns="product_name",
    values="total_quantity",   # FIXED HERE
    fill_value=0
)

print("✔ Pivot shape:", pivot.shape)

# ---------------------------------------------------
# Compute similarity matrix
# ---------------------------------------------------
similarity = cosine_similarity(pivot)
print("✔ Similarity matrix computed")

# ---------------------------------------------------
# Build product index maps
# ---------------------------------------------------
product_index = {product: i for i, product in enumerate(pivot.columns)}
reverse_index = {i: product for product, i in product_index.items()}

# ---------------------------------------------------
# Package model
# ---------------------------------------------------
model = {
    "pivot": pivot,
    "similarity": similarity,
    "product_index": product_index,
    "reverse_index": reverse_index,
    "customer_ids": list(pivot.index),
}

# ---------------------------------------------------
# Save model file
# ---------------------------------------------------
with open(MODEL_FILE, "wb") as f:
    pickle.dump(model, f)

print("\n🎉 MODEL TRAINED & SAVED SUCCESSFULLY!")
print("📁 Model file:", MODEL_FILE)
