import os
import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand
from django.db import connection
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
import pickle
from datetime import datetime


class Command(BaseCommand):
    help = "Train recommender and populate pest_recommendations table"

    def handle(self, *args, **kwargs):

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        trained_dir = os.path.join(base_dir, "trained_models")
        os.makedirs(trained_dir, exist_ok=True)

        print("📥 Fetching purchases from crmapp_purchasehistory...")

        df = pd.read_sql("""
            SELECT customer_id, product_id
            FROM crmapp_purchasehistory
            WHERE product_id IS NOT NULL AND customer_id IS NOT NULL
        """, connection)

        if df.empty:
            print("❌ No purchase history found. Cannot train.")
            return

        print(f"📊 Loaded {len(df)} purchase rows.")

        # Build customer-product matrix
        matrix = df.assign(count=1).pivot_table(
            index="customer_id",
            columns="product_id",
            values="count",
            aggfunc="sum",
            fill_value=0
        ).astype(np.float32)

        # -----------------------------
        # PART 1 – Product Similarity
        # -----------------------------
        print("🔍 Computing product similarity...")
        sim_matrix = cosine_similarity(matrix.T)

        sim_path = os.path.join(trained_dir, "recommender_similarity.pkl")
        with open(sim_path, "wb") as f:
            pickle.dump(
                {
                    "products": list(matrix.columns),
                    "similarity": sim_matrix
                },
                f
            )

        print(f"✅ Saved similarity model → {sim_path}")

        # -----------------------------
        # PART 2 – SVD Latent Factors
        # -----------------------------
        print("⚡ Running SVD...")
        svd = TruncatedSVD(n_components=50, random_state=42)

        latent_users = svd.fit_transform(matrix)
        scores = np.dot(latent_users, svd.components_)

        # Save CSV
        score_rows = []
        customers = list(matrix.index)
        products = list(matrix.columns)

        for i, cust in enumerate(customers):
            for j, prod in enumerate(products):
                score_rows.append((cust, prod, float(scores[i, j])))

        score_df = pd.DataFrame(score_rows, columns=["customerid", "productid", "score"])

        csv_path = os.path.join(trained_dir, "recommender_scores.csv")
        score_df.to_csv(csv_path, index=False)

        print(f"✅ Saved latent scoring → {csv_path}")

        # -----------------------------
        # PART 3 – Populate pest_recommendations
        # -----------------------------
        print("📝 Writing top recommendations to pest_recommendations...")

        with connection.cursor() as cur:
            cur.execute("TRUNCATE TABLE pest_recommendations")

            now = datetime.now()

            for cust in customers:
                top = (
                    score_df[score_df["customerid"] == cust]
                    .sort_values("score", ascending=False)
                    .head(10)
                )

                for _, row in top.iterrows():
                    cur.execute("""
                        INSERT INTO pest_recommendations
                        (customer_id, base_product_id, recommended_product_id, recommendation_type, confidence_score, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [
                        cust,
                        None,                   # base product not needed for personalized
                        int(row["productid"]),
                        "personalized",
                        round(row["score"], 2),
                        now
                    ])

        print("🎉 Training + DB population completed successfully!")
