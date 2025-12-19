import os
import sys
import django
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "crm"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")
django.setup()

from crmapp.models import PurchaseHistory, customer_details


def export_training_data():
    print("📥 Exporting clean dataset...")

    rows = []

    for p in PurchaseHistory.objects.all():
        # Match using customerid (string code)
        cust = customer_details.objects.filter(customerid=p.customer_id).first()

        if not cust:
            continue

        rows.append({
            "customer_id": cust.id,                     # numeric primary key for ML
            "customer_code": p.customer_id,             # original string code
            "product_id": p.product._get_pk_val() if p.product else None,   # FIXED
            "product_name": p.product_name,
            "quantity": float(p.quantity),
            "total_amount": float(p.total_amount),
            "invoice_type": p.invoice_type,
            "timestamp": p.purchased_at
        })

    df = pd.DataFrame(rows)
    df.to_csv("clean_training_data.csv", index=False)

    print("📊 Total rows exported:", len(df))
    print("✅ Clean dataset exported: clean_training_data.csv")


if __name__ == "__main__":
    export_training_data()
