from crmapp.models import ServiceCatalog, ServiceProduct
from recommender.models import PestRecommendation
 


def generate_service_recommendations(customer_id, intent, top_n=5):

    # 1️⃣ Get recommended products FOR THIS INTENT
    product_ids = PestRecommendation.objects.filter(
        canonical_customer_id=customer_id,
        reco_channel="product",
        business_intent=intent,   # 🔥 FIX
        is_active=1
    ).values_list("recommended_product_id", flat=True)

    if not product_ids:
        return []

    # 2️⃣ Get linked services via mapping table
    service_ids = (
        ServiceProduct.objects
        .filter(product_id__in=product_ids)
        .values_list("service_id", flat=True)
        .distinct()
    )

    # 3️⃣ Fetch active services
    services = (
        ServiceCatalog.objects
        .filter(service_id__in=service_ids, active=1)
        [:top_n]
    )

    # 4️⃣ Build output
    results = []
    base_score = 0.85

    for idx, s in enumerate(services):
        results.append({
            "service_id": s.service_id,
            "intent": intent,
            "score": round(base_score - idx * 0.03, 3)
        })

    return results
