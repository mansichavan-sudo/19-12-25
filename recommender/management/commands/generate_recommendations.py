from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

import joblib
import os

from crmapp.models import PurchaseHistory, service_management
from recommender.models import PestRecommendation


class Command(BaseCommand):
    help = "Generate Product + Service Recommendations"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Generating Product & Service recommendations..."))

        # =====================================================
        # LOAD MODELS
        # =====================================================
        model_path = os.path.join(
            settings.BASE_DIR,
            "recommender",
            "trained_models"
        )

        product_model = joblib.load(
            os.path.join(model_path, "recommender_model.pkl")
        )
        service_model = joblib.load(
            os.path.join(model_path, "service_recommender.pkl")
        )

        # =====================================================
        # PRODUCT RECOMMENDATIONS
        # =====================================================
        product_customers = (
            PurchaseHistory.objects
            .filter(purchase_type="PRODUCT")
            .values_list("customer_id", flat=True)
            .distinct()
        )

        product_recos = []
        product_created = 0

        for customer_id in product_customers:
            try:
                recs = product_model.recommend(
                    customer_id=customer_id,
                    n_recommendations=5
                )
            except Exception:
                continue

            for product_id, score in recs:

                # ❌ Skip if already recommended or served
                if PestRecommendation.objects.filter(
                    customer_id=customer_id,
                    recommended_product_id=product_id,
                    serving_state__in=["pending", "served"]
                ).exists():
                    continue

                product_recos.append(
                    PestRecommendation(
                        customer_id=customer_id,
                        recommended_product_id=product_id,

                        recommendation_type="upsell",
                        reco_channel="product",

                        algorithm_strategy="collaborative",
                        model_source="product_cf",

                        confidence_score=round(float(score), 2),
                        final_score=round(float(score), 3),

                        serving_state="pending",
                        valid_from=timezone.now(),
                        priority=50,
                    )
                )

                product_created += 1

        PestRecommendation.objects.bulk_create(product_recos)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Product recommendations created: {product_created}")
        )

        # =====================================================
        # SERVICE RECOMMENDATIONS
        # =====================================================
        service_customers = (
            service_management.objects
            .filter(contract_status__in=["Active", "Completed"])
            .values_list("customer_id", flat=True)
            .distinct()
        )

        service_recos = []
        service_created = 0

        for customer_id in service_customers:
            try:
                recs = service_model.recommend(
                    customer_id=customer_id,
                    top_n=3
                )
            except Exception:
                continue

            for service_id, score in recs:

                # ❌ Skip if already recommended or served
                if PestRecommendation.objects.filter(
                    customer_id=customer_id,
                    recommended_service_id=service_id,
                    serving_state__in=["pending", "served"]
                ).exists():
                    continue

                service_recos.append(
                    PestRecommendation(
                        customer_id=customer_id,
                        recommended_service_id=service_id,

                        recommendation_type="crosssell",
                        reco_channel="service",

                        algorithm_strategy="content",
                        model_source="service_model",

                        confidence_score=round(float(score), 2),
                        final_score=round(float(score), 3),

                        serving_state="pending",
                        valid_from=timezone.now(),
                        priority=80,
                    )
                )

                service_created += 1

        PestRecommendation.objects.bulk_create(service_recos)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Service recommendations created: {service_created}")
        )

        self.stdout.write(
            self.style.SUCCESS("🎉 ALL RECOMMENDATIONS GENERATED SUCCESSFULLY")
        )
