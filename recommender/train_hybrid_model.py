import os
import sys
import django
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import pickle

# --- Django setup ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "crm"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")
django.setup()

# Import your hybrid model class
from recommender.hybrid_model import HybridRecommender


# ------------------------------------------------------------
# Load Data
# ------------------------------------------------------------
def load_training_data():
    print("📥 Loading training data...")
    df = pd.read_csv("final_ml_training.csv")
    print("📊 Loaded rows:", len(df))
    return df


# ------------------------------------------------------------
# Train Collaborative Filtering Model
# ------------------------------------------------------------
def train_cf_model(df):
    print("🔧 Training Collaborative Filtering model...")

    if "rating" not in df.columns:
        print("⚠️ No 'rating' column found — using 'quantity' as rating.")
        df["rating"] = df["quantity"]

    user_item_matrix = df.pivot_table(
        index="customer_id",
        columns="product_id",
        values="rating",
        aggfunc="sum"
    ).fillna(0)

    similarity_matrix = cosine_similarity(user_item_matrix)

    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=user_item_matrix.index,
        columns=user_item_matrix.index
    )

    print("✅ CF model trained.")

    return {
        "user_item_matrix": user_item_matrix,
        "similarity_df": similarity_df
    }


# ------------------------------------------------------------
# Build the Hybrid Model Object
# ------------------------------------------------------------
def build_hybrid(cf_model):
    print("🔀 Building HybridRecommender object...")
    hybrid = HybridRecommender(cf_model=cf_model, content_model=None)
    return hybrid


# ------------------------------------------------------------
# Save Model
# ------------------------------------------------------------
def save_model(model, filename):
    MODEL_DIR = "recommender/trained_models"
    os.makedirs(MODEL_DIR, exist_ok=True)

    path = os.path.join(MODEL_DIR, filename)
    with open(path, "wb") as f:
        pickle.dump(model, f)

    print(f"💾 Saved: {path}")


# ------------------------------------------------------------
# Main Training
# ------------------------------------------------------------
def train_hybrid_model():
    print("\n🚀 STARTING HYBRID TRAINING...")

    df = load_training_data()
    if df.empty:
        print("❌ No data found!")
        return

    # 1) Train CF
    cf_model = train_cf_model(df)

    # 2) Build HybridRecommender()
    hybrid_model = build_hybrid(cf_model)

    # 3) Save both models
    save_model(cf_model, "cf_model.pkl")
    save_model(hybrid_model, "hybrid_recommender.pkl")

    print("\n🎉 TRAINING COMPLETE — HybridRecommender Ready!\n")


if __name__ == "__main__":
    train_hybrid_model()
