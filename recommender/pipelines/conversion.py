from django.utils import timezone
from recommender.models import PestRecommendation


def mark_recommendation_converted(
    customer_id,
    product_id=None,
    service_id=None,
    revenue=0.0
):
    """
    Marks the most recent ACTIVE recommendation as converted
    """

    qs = PestRecommendation.objects.filter(
        customer_fk=customer_id,
        serving_state="accepted",
        converted_at__isnull=True
    )

    if product_id:
        qs = qs.filter(recommended_product_id=product_id)

    if service_id:
        qs = qs.filter(recommended_service_id=service_id)

    rec = qs.order_by("-served_at").first()
    if not rec:
        return None

    rec.converted_at = timezone.now()
    rec.revenue_amount = revenue
    rec.serving_state = "accepted"

    rec.save(update_fields=[
        "converted_at",
        "revenue_amount",
        "serving_state"
    ])

    return rec
