from recommender.models import PestRecommendation

def save_service_recommendations(customer_id, services, intent):
    rows = []

    for svc in services:
        rows.append(PestRecommendation(
            canonical_customer_id=customer_id,
            customer_fk=customer_id,
            reco_channel="service",
            recommended_service_id=svc["service_id"],
            business_intent=intent,
            recommendation_type="hybrid",
            algorithm_strategy="rule_based",
            confidence_score=svc.get("score", 0.75),
            final_score=svc.get("score", 0.75),
            serving_state="pending",
            is_active=1,
            model_source="pipeline",
            allowed_channels="ai_call,whatsapp,email",
            consent_call=1,
            consent_whatsapp=1,
            consent_email=1
        ))

    PestRecommendation.objects.bulk_create(rows)
