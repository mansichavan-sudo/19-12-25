from crmapp.models import PurchaseHistory
from django.db.models import Count

def collaborative_recommendations(customer_id, top_n=10):
    user_products = PurchaseHistory.objects.filter(
        customer_id=customer_id
    ).values_list("product_id", flat=True)

    if not user_products:
        return []

    similar_customers = PurchaseHistory.objects.filter(
        product_id__in=user_products
    ).exclude(customer_id=customer_id).values_list("customer_id", flat=True)

    qs = (
        PurchaseHistory.objects
        .filter(customer_id__in=similar_customers)
        .exclude(product_id__in=user_products)
        .values("product_id")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    return [
        {
            "product_id": row["product_id"],
            "score": float(row["freq"]),
            "method": "cf",
            "reason": "Customers with similar purchases also bought this"
        }
        for row in qs
    ]
