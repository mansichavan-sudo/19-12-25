def cross_sell_recommendations(customer_id, top_n=5):
    from crmapp.models import PurchaseHistory
    from django.db.models import Count

    purchased = PurchaseHistory.objects.filter(
        customer_id=customer_id
    ).values_list("product_id", flat=True)

    if not purchased:
        return []

    qs = (
        PurchaseHistory.objects
        .filter(product_id__in=purchased)
        .exclude(customer_id=customer_id)
        .values("product_id")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    return [
        {
            "product_id": row["product_id"],
            "score": float(row["freq"]),
            "method": "cross_sell",
            "reason": "Frequently bought together"
        }
        for row in qs
    ]
