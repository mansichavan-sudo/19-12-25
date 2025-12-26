from django.db.models import Max, Avg, DecimalField
from django.db.models.functions import Coalesce
from crmapp.models import customer_details
from recommender.models import PestRecommendation
from crmapp.models import ServiceProduct


def fetch_upsell(customer):
    # PRODUCTS
    product_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="upsell",
            recommended_product__isnull=False
        )
        .values(
            "recommended_product__product_id",
            "recommended_product__product_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:7]
    )

    products = []
    for p in product_qs:
        avg_price = (
            ServiceProduct.objects
            .filter(product_id=p["recommended_product__product_id"])
            .aggregate(
                avg=Coalesce(
                    Avg("price"),
                    0,
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )["avg"]
        )

        products.append({
            "id": p["recommended_product__product_id"],
            "name": p["recommended_product__product_name"],
            "confidence": float(p["confidence"]),
            "average_price": float(round(avg_price, 2))
        })

    # SERVICES
    service_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="upsell",
            recommended_service__isnull=False
        )
        .values(
            "recommended_service__service_id",
            "recommended_service__service_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:3]
    )

    services = [
        {
            "id": s["recommended_service__service_id"],
            "name": s["recommended_service__service_name"],
            "confidence": float(s["confidence"])
        }
        for s in service_qs
    ]

    return {"products": products, "services": services}


def fetch_crosssell(customer):
    product_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="crosssell",
            recommended_product__isnull=False
        )
        .values(
            "recommended_product__product_id",
            "recommended_product__product_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:7]
    )

    products = [
        {
            "id": p["recommended_product__product_id"],
            "name": p["recommended_product__product_name"],
            "confidence": float(p["confidence"])
        }
        for p in product_qs
    ]

    service_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="crosssell",
            recommended_service__isnull=False
        )
        .values(
            "recommended_service__service_id",
            "recommended_service__service_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:3]
    )

    services = [
        {
            "id": s["recommended_service__service_id"],
            "name": s["recommended_service__service_name"],
            "confidence": float(s["confidence"])
        }
        for s in service_qs
    ]

    return {"products": products, "services": services}
