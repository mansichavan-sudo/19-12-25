from recommender.models import PestRecommendation
from django.utils.timezone import now


def persist_recommendations(customer_id, ranked):
    """
    Persist final ranked recommendations.
    This function NEVER deletes historical data.
    """

    objs = []

    for r in ranked:
        objs.append(
            PestRecommendation(
                customer_id=customer_id,
                recommended_product_id=r["product_id"],
                recommendation_type=r["method"],
                final_score=r["score"],
                algorithm_strategy="hybrid",
                model_source="v1",
                priority=r["rank"],
                serving_state="pending",
                valid_from=now(),
            )
        )

    if objs:
        PestRecommendation.objects.bulk_create(objs)
