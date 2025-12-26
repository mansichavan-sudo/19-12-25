from django.core.management.base import BaseCommand
from django.utils import timezone

from crmapp.models import service_management
from recommender.models import PestRecommendation

import joblib
import os


MODEL_PATH = os.path.join(
    "recommender",
    "trained_models",
    "service_recommender.pkl"
)


class Command(BaseCommand):
    help = "Generate SERVICE recommendations for customers"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Generating service recommendations..."))

        # --------------------------------------------------
        # Load trained SERVICE model
        # --------------------------------------------------
        if not os.path.exists(MODEL_PATH):
            raise Exception("❌ Service model not found. Please run train_models first.")

        try:
            model = joblib.load(MODEL_PATH)
        except Exception as e:
            raise Exception(f"❌ Failed to load service model: {e}")

        # --------------------------------------------------
        # Build customer → already used services map
        # --------------------------------------------------
        qs = service_management.objects.filter(
            customer_id__isnull=False,
            contract_status__in=["Active", "Completed"]
        )

        customer_services = {}

        for s in qs:
            customer_services.setdefault(s.customer_id, set()).add(s.id)

        # --------------------------------------------------
        # Generate recommendations
        # --------------------------------------------------
        created = 0

        for customer_id, taken_services in customer_services.items():

            try:
                recommendations = model.recommend(
                    customer_id=customer_id,
                    top_n=5
                )
            except Exception:
                # Skip customers not present in model
                continue

            for service_id, score in recommendations:

                # Skip already taken services
                if service_id in taken_services:
                    continue

                # Avoid duplicate pending recommendations
                if PestRecommendation.objects.filter(
                    customer_fk=customer_id,
                    recommended_service_id=service_id,
                    reco_channel="service",
                    serving_state="pending",
                ).exists():
                    continue

                PestRecommendation.objects.create(
                    customer_fk=customer_id,
                    customer_id=str(customer_id),

                    recommended_service_id=service_id,
                    reco_channel="service",

                    recommendation_type="upsell",
                    business_intent="upsell",

                    algorithm_strategy="collaborative",
                    model_source="service_cf",

                    confidence_score=round(float(score), 2),
                    final_score=round(float(score), 3),

                    created_at=timezone.now(),
                    valid_from=timezone.now(),

                    serving_state="pending",
                    allowed_channels="whatsapp,email",
                    priority=80,
                )

                created += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ {created} service recommendations created")
        )
