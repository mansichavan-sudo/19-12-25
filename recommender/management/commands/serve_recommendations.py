from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from recommender.models import PestRecommendation


class Command(BaseCommand):
    help = "Serve best recommendation (product/service) per customer"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting recommendation serving..."))

        # --------------------------------------------------
        # Step 1: Find customers with pending recommendations
        # --------------------------------------------------
        customer_ids = (
            PestRecommendation.objects
            .filter(serving_state="pending")
            .exclude(customer__isnull=True)     # ✅ FIX
            .values_list("customer_id", flat=True)  # Django auto FK id
            .distinct()
        )

        served_count = 0

        # --------------------------------------------------
        # Step 2: Serve ONE best recommendation per customer
        # --------------------------------------------------
        for customer_id in customer_ids:

            rec = (
                PestRecommendation.objects
                .filter(
                    customer_id=customer_id,   # ✅ FIX
                    serving_state="pending",
                )
                .filter(
                    Q(valid_until__isnull=True) |
                    Q(valid_until__gte=timezone.now())
                )
                .order_by(
                    "priority",        # lower number = higher priority
                    "-final_score",    # higher score first
                    "created_at"       # older first
                )
                .select_related(
                    "customer",
                    "recommended_product",
                    "recommended_service"
                )
                .first()
            )

            if not rec:
                continue

            # --------------------------------------------------
            # Step 3: Mark as served
            # --------------------------------------------------
            rec.serving_state = "served"
            rec.served_at = timezone.now()
            rec.save(update_fields=["serving_state", "served_at"])

            served_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ {served_count} recommendations served successfully")
        )
