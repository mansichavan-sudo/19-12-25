from recommender.recommender_engine import recommend_cf
from recommender.demographic_service import get_demographic_recommendations


def get_hybrid_recommendations(customer_id, top_n=5):
    """
    Priority:
    1) CF (if available)
    2) Demographic fallback
    """

    cf_results = recommend_cf(customer_id, top_n)

    if cf_results:
        return {
            "method": "cf",
            "results": cf_results
        }

    demo = get_demographic_recommendations(customer_id, limit=top_n)

    return {
        "method": "demographic",
        "results": demo.get("recommended_products", [])
    }
