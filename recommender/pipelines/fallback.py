from crmapp.models import Product


def fallback_if_empty(customer_id, ranked, top_k=5):
    """
    Cold-start fallback: popular products
    """
    if ranked:
        return ranked

    products = (
        Product.objects
        .filter(is_active=True)
        .order_by("-created_at")[:top_k]
    )

    fallback = []
    for i, p in enumerate(products, start=1):
        fallback.append({
            "product_id": p.id,
            "score": 0.10,
            "method": "fallback",
            "explanation": "Popular product fallback",
            "priority": 999,
            "rank": i,
        })

    return fallback
