import pickle
import numpy as np
import pandas as pd
from django.conf import settings
from crmapp.models import Product, PurchaseHistory, customer_details

MODEL_PATH = "recommender/trained_models/simple_cf_model.pkl"

class RecommendationEngine:

    def __init__(self):
        print("📥 Loading trained recommendation model...")
        with open(MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)

        self.pivot = self.model["pivot"]
        self.similarity = self.model["similarity"]
        self.product_index = self.model["product_index"]
        self.reverse_index = self.model["reverse_index"]

        print("✅ Model loaded successfully.")

    def recommend_for_customer(self, customer_id, top_n=5):
        """
        Input: real customer_id (example 'MAHWAG4376')
        Output: list of recommended Product objects
        """

        # ------------------------------
        # 1️⃣ Convert real customer_id → internal pivot row
        # ------------------------------
        if customer_id not in self.pivot.index:
            print("⚠ Customer not found in training pivot, generating cold-start fallback.")
            return self._cold_start_recommendation()

        customer_row = self.pivot.index.get_loc(customer_id)

        # ------------------------------
        # 2️⃣ Find similar customers
        # ------------------------------
        similarity_scores = list(enumerate(self.similarity[customer_row]))
        similarity_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)

        # Top neighbors
        neighbors = [idx for idx, score in similarity_scores[1:6]]

        # ------------------------------
        # 3️⃣ Aggregate neighbor preferences
        # ------------------------------
        neighbor_matrix = self.pivot.iloc[neighbors]
        summed_scores = neighbor_matrix.sum(axis=0)

        # Remove already purchased items
        already_bought = set(self.pivot.loc[customer_id][self.pivot.loc[customer_id] > 0].index)
        recommendations = summed_scores.drop(labels=already_bought, errors="ignore")

        # ------------------------------
        # 4️⃣ Pick top N products
        # ------------------------------
        top_products = recommendations.sort_values(ascending=False).head(top_n)

        product_names = list(top_products.index)

        # Return actual Product objects
        return Product.objects.filter(productname__in=product_names)

    # ------------------------------
    # Cold-start: If customer has no history
    # ------------------------------
    def _cold_start_recommendation(self, top_n=5):
        print("ℹ Using fallback cold-start recommendations…")
        return Product.objects.all().order_by("-popularity")[:top_n]
