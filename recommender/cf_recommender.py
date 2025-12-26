import pickle
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "trained_models", "cf_model.pkl")


def load_cf_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("CF model not trained yet")

    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def recommend_cf_products(customer_id, top_n=5):
    """
    Returns CF-based product recommendations
    """
    model = load_cf_model()

    user_item_matrix = model["user_item_matrix"]
    similarity_df = model["similarity_df"]

    if customer_id not in similarity_df.index:
        return []

    # ---- find similar users ----
    similar_users = (
        similarity_df.loc[customer_id]
        .drop(customer_id)
        .sort_values(ascending=False)
        .head(5)
        .index
    )

    # ---- aggregate scores ----
    scores = (
        user_item_matrix.loc[similar_users]
        .mean()
        .sort_values(ascending=False)
    )

    # ---- remove already purchased ----
    already_bought = user_item_matrix.loc[customer_id]
    scores = scores[already_bought == 0]

    recommendations = []
    for product_id, score in scores.head(top_n).items():
        recommendations.append({
            "type": "product",
            "product_id": int(product_id),
            "reason": "Customers with similar behavior purchased this",
            "score": float(score)
        })

    return recommendations
