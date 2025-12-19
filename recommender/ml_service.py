import os
import pickle
from django.conf import settings
import numpy as np
import pandas as pd


# -------------------------------------------------------------------
# Load Model
# -------------------------------------------------------------------
MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "recommender",
    "trained_models",
    "recommender_model.pkl"
)

print(f"📥 Loading Recommendation Model: {MODEL_PATH}")

try:
    with open(MODEL_PATH, "rb") as f:
        model_data = pickle.load(f)

    pivot = model_data["pivot"]
    similarity = model_data["similarity"]

    print("✅ CF Model Loaded Successfully")

except Exception as e:
    print(f"❌ ERROR loading ML model: {e}")
    model_data = None
    pivot = None
    similarity = None


# -------------------------------------------------------------------
# Recommendation Algorithm (Collaborative Filtering)
# -------------------------------------------------------------------
def generate_recommendations(customer_id):
    """
    CF similarity-based recommendation engine.
    """

    if pivot is None or similarity is None:
        return []

    try:
        customer_id = int(customer_id)
    except:
        return []

    # Customer not found
    if customer_id not in pivot.index:
        return []

    # Get the similarity scores for this user
    user_index = pivot.index.get_loc(customer_id)
    sim_scores = similarity[user_index]

    # Sort users by similarity (descending)
    similar_users_indices = sim_scores.argsort()[::-1]

    recommended_products = set()

    # Iterate over top similar users
    for idx in similar_users_indices[1:10]:  # skip itself
        similar_user_id = pivot.index[idx]

        # Get products purchased by similar user
        user_products = pivot.columns[pivot.loc[similar_user_id] > 0]

        for p in user_products:
            recommended_products.add(p)

        # Cap recommendations to avoid huge list
        if len(recommended_products) >= 10:
            break

    # Remove products the customer already bought
    already_bought = pivot.columns[pivot.loc[customer_id] > 0]
    final_recommendations = [
        p for p in recommended_products if p not in already_bought
    ]

    return final_recommendations[:10]


# -------------------------------------------------------------------
# API Wrapper
# -------------------------------------------------------------------
def get_recommendations_for_customer(customer_id):
    return generate_recommendations(customer_id)


def get_recommendations(customer_id):
    return generate_recommendations(customer_id)
