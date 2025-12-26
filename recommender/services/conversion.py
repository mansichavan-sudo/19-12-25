# recommender/services/conversion.py
from django.utils import timezone
from recommender.models import PestRecommendation

def mark_converted(
    reco_id,
    revenue,
    product_id=None,
    service_id=None
):
    return PestRecommendation.objects.filter(
        id=reco_id,
        serving_state__in=["served", "accepted"]
    ).update(
        serving_state="accepted",
        converted_at=timezone.now(),
        converted_product_id=product_id,
        converted_service_id=service_id,
        revenue_amount=revenue
    )
