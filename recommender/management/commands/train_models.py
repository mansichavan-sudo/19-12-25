from django.core.management.base import BaseCommand
from datetime import date
import pandas as pd

from recommender.training.train_cf import train_cf_model
from recommender.training.train_content import train_content_model
from recommender.training.train_service_model import train_service_model

from crmapp.models import PurchaseHistory, service_management


def normalize_frequency(value):
    """
    Convert service frequency text into numeric value
    """
    if not value:
        return 1

    value = str(value).strip().lower()

    mapping = {
        "one time": 1,
        "once": 1,
        "fortnight": 2,
        "biweekly": 2,
        "monthly": 4,
        "quarterly": 3,
        "half yearly": 6,
        "yearly": 12,
        "annual": 12,
        "amc": 12,
    }

    if value in mapping:
        return mapping[value]

    # If already numeric
    try:
        return int(value)
    except ValueError:
        return 1


class Command(BaseCommand):
    help = "Train Product + Service Recommendation Models"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔵 Starting model training..."))

        # ==========================================================
        # STEP 1: PRODUCT DATA (CF + CONTENT)
        # ==========================================================
        product_qs = PurchaseHistory.objects.filter(
            purchase_type="PRODUCT",
            product_id__isnull=False,
        )

        product_rows = []
        for p in product_qs:
            product_rows.append({
                "customer_id": p.customer_int or p.customer_ref,
                "product_id": p.product_id,
                "frequency": float(p.quantity or 1),
                "monetary": float(p.total_amount or 0),
                "recency": 1,
            })

        product_df = pd.DataFrame(product_rows)

        if product_df.empty:
            self.stdout.write(self.style.WARNING("⚠ No product purchase data"))
        else:
            train_cf_model(product_df)
            self.stdout.write(self.style.SUCCESS("✅ Product CF model trained"))

            train_content_model(product_df)
            self.stdout.write(self.style.SUCCESS("✅ Product Content model trained"))

        # ==========================================================
        # STEP 2: SERVICE DATA
        # ==========================================================
        service_qs = service_management.objects.filter(
            customer_id__isnull=False,
            contract_status__in=["Active", "Completed"]
        )

        service_rows = []
        today = date.today()

        for s in service_qs:
            if not s.service_subject:
                continue

            recency = (
                (today - s.service_date).days
                if s.service_date else 999
            )

            service_rows.append({
                "customer_id": s.customer_id,
                "service_id": s.id,
                "frequency": normalize_frequency(s.frequency_count),
                "monetary": float(s.total_price_with_gst or 0),
                "recency": recency,
            })

        service_df = pd.DataFrame(service_rows)

        if service_df.empty:
            self.stdout.write(self.style.WARNING("⚠ No service data found"))
        else:
            train_service_model(service_df)
            self.stdout.write(self.style.SUCCESS("✅ Service model trained"))

        self.stdout.write(self.style.SUCCESS("🎉 ALL MODELS TRAINED SUCCESSFULLY"))
