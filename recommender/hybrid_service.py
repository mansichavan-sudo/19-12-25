import os
import pickle
from django.conf import settings
from .demographic_service import DemographicRecommender

MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "recommender",
    "trained_models",
    "hybrid_recommender.pkl"
)

print(f"📥 Loading Hybrid Recommendation Model: {MODEL_PATH}")

try:
    with open(MODEL_PATH, "rb") as f:
        hybrid_model = pickle.load(f)

    print("✅ HybridRecommender Loaded Successfully")

except Exception as e:
    print("❌ Hybrid Model Load Error:", e)
    hybrid_model = None


def get_hybrid_recommendations(customer_id, top_n=10):
    """
    Hybrid → if fails → fallback to demographic
    """
    if hybrid_model is None:
        print("⚠ Using demographic fallback (model missing)")
        demo = DemographicRecommender.recommend_for_customer(customer_id, limit=top_n)
        return demo["recommended_products"]

    try:
        customer_id = int(customer_id)
        hybrid_results = hybrid_model.recommend(customer_id, top_n=top_n)

        if not hybrid_results:
            print("⚠ Hybrid returned empty — fallback")
            demo = DemographicRecommender.recommend_for_customer(customer_id, limit=top_n)
            return demo["recommended_products"]

        return hybrid_results

    except Exception as e:
        print("⚠ Hybrid crashed — fallback:", e)
        demo = DemographicRecommender.recommend_for_customer(customer_id, limit=top_n)
        return demo["recommended_products"]
