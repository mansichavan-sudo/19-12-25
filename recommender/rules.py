# recommender/rules.py

from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from crmapp.models import PurchaseHistory, Product


def rule_based_recommendations(customer_id):
    recs = []

    # 1️⃣ Recently purchased products (repeat / refill logic)
    recent_products = (
        PurchaseHistory.objects
        .filter(
            customer_id=customer_id,
            product_id__isnull=False,
            purchased_at__gte=timezone.now() - timedelta(days=90)
        )
        .values_list("product_id", flat=True)
    )

    recs += Product.objects.filter(id__in=recent_products)

    # 2️⃣ Popular fallback
    popular = (
        PurchaseHistory.objects
        .filter(product_id__isnull=False)
        .values("product_id")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:5]
    )

    recs += Product.objects.filter(
        id__in=[p["product_id"] for p in popular]
    )

    # Remove duplicates, limit
    return list(dict.fromkeys(recs))[:5]
