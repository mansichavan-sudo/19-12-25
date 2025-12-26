from crmapp.models import Product, ServiceProduct
from django.db.models import Avg
from django.db.models.functions import Coalesce

def upsell_recommendations(product_id, top_n=3):
    base_price = (
        ServiceProduct.objects
        .filter(product_id=product_id)
        .aggregate(price=Coalesce(Avg("price"), 0))["price"]
    )

    qs = (
        Product.objects
        .annotate(avg_price=Coalesce(Avg("serviceproduct__price"), 0))
        .filter(avg_price__gt=base_price)
        .order_by("avg_price")[:top_n]
    )

    return [
        {
            "product_id": p.product_id,
            "score": float(p.avg_price),
            "method": "upsell",
            "reason": "Higher priced premium option"
        }
        for p in qs
    ]
