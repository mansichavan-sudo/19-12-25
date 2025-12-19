# recommender/predictor.py

import pickle
import numpy as np

MODEL_PATH = "recommender/trained_models/simple_cf_model.pkl"

# ---------------------------
# Load Model
# ---------------------------
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

pivot = model["pivot"]
similarity = model["similarity"]

# ---------------------------
# Recommend Products
# ---------------------------
def recommend_products(customer_id, top_n=5):
    if customer_id not in pivot.index:
        return []  # no history → no recommendations

    # get index of customer
    idx = pivot.index.tolist().index(customer_id)

    # similarity vector
    sim_vector = similarity[idx]

    # weighted scoring
    scores = np.dot(sim_vector, pivot.values)

    # remove already bought
    scores = scores - pivot.loc[customer_id].values * 999

    # best product indices
    best_indices = np.argsort(scores)[::-1][:top_n]

    # convert index → product_ids
    product_ids = pivot.columns[best_indices].tolist()

    return product_ids
