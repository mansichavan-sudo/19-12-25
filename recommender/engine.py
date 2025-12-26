import pickle
import numpy as np
import os

# -------------------------------------------------------------
# LOAD TRAINED MODEL AUTOMATICALLY
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, "trained_models", "recommender_model.pkl")

with open(MODEL_FILE, "rb") as f:
    model = pickle.load(f)

pivot = model["pivot"]
similarity = model["similarity"]
customer_ids = model["customer_ids"]


# -------------------------------------------------------------
# FUNCTION TO GET RECOMMENDATIONS
# -------------------------------------------------------------
def get_recommendations(customer_id, top_n=5):
    if customer_id not in pivot.index:
        return []  # Customer not found

    # Get index of the customer in the pivot matrix
    customer_index = list(pivot.index).index(customer_id)

    # Fetch similarity row for this customer
    similarity_scores = similarity[customer_index]

    # Sort by highest similarity (descending)
    similar_customers = np.argsort(similarity_scores)[::-1]

    # Get current customer's purchased products
    customer_products = set(pivot.columns[pivot.loc[customer_id] > 0])

    recommended = []

    # Loop through similar customers
    for idx in similar_customers:
        if idx == customer_index:
            continue  # Skip self

        other_customer_id = pivot.index[idx]

        # Products purchased by similar customer
        other_products = set(pivot.columns[pivot.loc[other_customer_id] > 0])

        # Recommend products they bought but our customer hasn't
        new_products = list(other_products - customer_products)

        for product in new_products:
            if product not in recommended:
                recommended.append(product)

        if len(recommended) >= top_n:
            break

    return recommended[:top_n]

import pickle
import numpy as np
import os

# -------------------------------------------------------------
# LOAD TRAINED MODEL AUTOMATICALLY
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, "trained_models", "recommender_model.pkl")

with open(MODEL_FILE, "rb") as f:
    model = pickle.load(f)

pivot = model["pivot"]
similarity = model["similarity"]
customer_ids = model["customer_ids"]

# -------------------------------------------------------------
# COLLABORATIVE FILTERING RECOMMENDATIONS
# -------------------------------------------------------------
def cf_get_recommendations(customer_id, top_n=5):
    if customer_id not in pivot.index:
        return []

    customer_index = list(pivot.index).index(customer_id)
    similarity_scores = similarity[customer_index]
    similar_customers = np.argsort(similarity_scores)[::-1]

    customer_products = set(pivot.columns[pivot.loc[customer_id] > 0])
    recommended = []

    for idx in similar_customers:
        if idx == customer_index:
            continue

        other_customer_id = pivot.index[idx]
        other_products = set(pivot.columns[pivot.loc[other_customer_id] > 0])

        new_products = other_products - customer_products

        for product in new_products:
            if product not in recommended:
                recommended.append(product)

        if len(recommended) >= top_n:
            break

    return recommended[:top_n]
