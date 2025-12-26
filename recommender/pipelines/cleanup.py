from django.utils import timezone
from recommender.models import PestRecommendation


def expire_existing_services(customer_id: int, intent: str):
    PestRecommendation.objects.filter(
        canonical_customer_id=customer_id,
        business_intent=intent,
        reco_channel="service",
        is_active=1,
    ).update(
        is_active=0,
        serving_state="expired",
        valid_until=timezone.now(),
    )
