# recommender/ml/recommender_engine.py

import os
import pickle
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "trained_models", "simple_cf_model.pkl")


# ------------------------------------------------------------
# Load saved ML model (pivot table + similarity matrix)
# ------------------------------------------------------------
def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"ML model file not found at: {MODEL_PATH}")

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    # Required keys
    required = ["pivot", "similarity", "index_map", "product_ids"]

    for key in required:
        if key not in model:
            raise ValueError(f"Model file is missing key: {key}")

    return model


# ------------------------------------------------------------
# Core recommendation logic
# ------------------------------------------------------------
def recommend_products(customer_id, top_n=5):
    """
    Returns recommended products for a given customer_id.
    Output format:
    [
        {"product_id": 104, "score": 0.87},
        {"product_id": 105, "score": 0.82}
    ]
    """

    try:
        model = load_model()
    except Exception as e:
        return {"status": "error", "message": str(e), "recommendations": []}

    pivot = model["pivot"]
    similarity = model["similarity"]
    index_map = model["index_map"]
    product_ids = model["product_ids"]

    # --------------------------------------------------------
    # Handle missing customer_id (cold start)
    # --------------------------------------------------------
    if customer_id not in index_map:
        return {
            "status": "cold_start",
            "message": "Customer has no purchase history.",
            "recommendations": []
        }

    # --------------------------------------------------------
    # Find index in similarity matrix
    # --------------------------------------------------------
    customer_index = index_map[customer_id]

    # Vector of similarity scores
    similarity_scores = list(enumerate(similarity[customer_index]))

    # Sort similar customers
    similarity_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)

    # Remove self (first element)
    similarity_scores = similarity_scores[1:20]

    # --------------------------------------------------------
    # Weighted score aggregation
    # --------------------------------------------------------
    customer_row = pivot.iloc[customer_index]

    scores = {}

    for idx, sim in similarity_scores:
        if sim <= 0:
            continue

        neighbor = pivot.iloc[idx]

        for product_name, quantity in neighbor.items():
            if quantity > 0 and customer_row[product_name] == 0:
                scores[product_name] = scores.get(product_name, 0) + (sim * quantity)

    if not scores:
        return {
            "status": "empty",
            "message": "No recommendations could be generated.",
            "recommendations": []
        }

    # Sort by score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Map product_name → product_id
    recommendations = []
    for product_name, score in sorted_scores[:top_n]:
        pid = product_ids.get(product_name)
        if pid:
            recommendations.append({
                "product_id": pid,
                "score": round(float(score), 4)
            })

    return {
        "status": "success",
        "customer_id": customer_id,
        "recommendations": recommendations
    }
