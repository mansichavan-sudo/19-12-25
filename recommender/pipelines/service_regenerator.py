import json
from crmapp.models import customer_details
from recommender.models import PestRecommendation
from recommender.engines.service_engine import generate_service_recommendations
from recommender.pipelines.cleanup import expire_existing_services


def regenerate_services(canonical_customer_id: int, intent: str = "crosssell"):

    customer = customer_details.objects.get(id=canonical_customer_id)

    # 1️⃣ Expire existing service recommendations
    expire_existing_services(
        customer_id=canonical_customer_id,
        intent=intent
    )

    # 2️⃣ Generate fresh services
    services = generate_service_recommendations(
        canonical_customer_id,
        intent
    )

    for s in services:
        PestRecommendation.objects.create(
            canonical_customer_id=customer.id,
            customer_fk=customer.id,
            customer_id=customer.customerid,

            recommended_service_id=s["service_id"],
            reco_channel="service",

            recommendation_type=intent,
            business_intent=intent,

            algorithm_strategy="rule_based",
            model_source="pipeline",

            confidence_score=s.get("score", 0.85),
            final_score=s.get("score", 0.85),
            priority=50,

            serving_state="pending",
            is_active=True,

            allowed_channels=json.dumps(["whatsapp", "email"]),
            consent_whatsapp=True,
            consent_email=True,
        )

    return len(services)
