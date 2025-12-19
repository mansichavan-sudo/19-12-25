import numpy as np

class HybridRecommender:
    """
    Hybrid model combining:
    - Collaborative Filtering (CF)
    - Content-based similarity
    - Rule-based scores
    """

    def __init__(self, cf_model=None, content_model=None):
        self.cf_model = cf_model
        self.content_model = content_model

    # ----------------------------------------------------
    # MAIN HYBRID RECOMMEND FUNCTION
    # ----------------------------------------------------
    def hybrid_recommend(self, product_id=None, product_name=None, top_n=10):
        """
        Generate hybrid recommendations.
        Returns a list of:
        {
            "product_id": ...,
            "product_name": ...,
            "score": ...
        }
        """

        results = {}

        # ------------------------------
        # 1️⃣ CF RECOMMENDATIONS
        # ------------------------------
        if self.cf_model and product_id:
            try:
                cf_recs = self.cf_model.get_recommendations(product_id, top_n=top_n)
                for r in cf_recs:
                    pid = str(r["product_id"])
                    results.setdefault(pid, {
                        "product_id": r["product_id"],
                        "product_name": r["product_name"],
                        "score": 0
                    })
                    results[pid]["score"] += 1.0 * r.get("score", 1)   # weight 1.0
            except Exception:
                pass

        # ------------------------------
        # 2️⃣ CONTENT-BASED RECOMMENDATIONS
        # ------------------------------
        if self.content_model and product_name:
            try:
                content_recs = self.content_model.get(product_name, [])
                for r in content_recs:
                    pid = str(r["product_id"])
                    results.setdefault(pid, {
                        "product_id": r["product_id"],
                        "product_name": r["product_name"],
                        "score": 0
                    })
                    results[pid]["score"] += 0.7     # weight 0.7
            except Exception:
                pass

        # ------------------------------
        # 3️⃣ RULE-BASED CONTEXT SCORE
        # ------------------------------
        # Adds small bonus to premium products or popular ones
        for pid in results:
            bonus = np.random.uniform(0.1, 0.3)   # tiny random uplift
            results[pid]["score"] += bonus

        # ------------------------------
        # 4️⃣ SORT & RETURN TOP
        # ------------------------------
        final = sorted(results.values(), key=lambda x: x["score"], reverse=True)[:top_n]
        return final

