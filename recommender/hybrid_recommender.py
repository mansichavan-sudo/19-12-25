from crmapp.models import Product
from recommender.cf_recommender import recommend_cf_products
from recommender.service_upsell import service_upsell_rules
from django.db.models import Count

from django.db.models import Count

def get_popular_products(top_n=3):
    products = (
        Product.objects
        .annotate(purchase_count=Count("purchase_history"))
        .order_by("-purchase_count")[:top_n]
    )

    return [
        {
            "type": "product",
            "product_id": p.pk,
            "reason": "Popular product",
            "score": 0.6
        }
        for p in products
    ]


def get_hybrid_recommendations(customer_id, top_n=5):
    recommendations = []

    # 1️⃣ CF recommendations
    cf_recs = recommend_cf_products(customer_id, top_n=top_n)
    print("CF RECS:", cf_recs)

    if not cf_recs:
        print("USING FALLBACK PRODUCTS")
        cf_recs = get_popular_products(top_n=3)

    recommendations.extend(cf_recs)

    # 2️⃣ Service upsell
    service_recs = service_upsell_rules(customer_id)
    recommendations.extend(service_recs)

    # 3️⃣ Sort by score
    recommendations = sorted(
        recommendations,
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    return recommendations[:top_n]
