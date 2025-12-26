import pickle
import os

from .cf_data_prep import load_cf_events, build_user_item_matrix, compute_user_similarity

MODEL_PATH = os.path.join("recommender", "trained_models", "cf_model.pkl")

def train_cf():
    df = load_cf_events()

    if df.empty:
        raise ValueError("No purchase data found")

    user_item = build_user_item_matrix(df)
    similarity = compute_user_similarity(user_item)

    model = {
        "user_item_matrix": user_item,
        "similarity_df": similarity,
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print("✅ CF model trained & saved")

    return model
