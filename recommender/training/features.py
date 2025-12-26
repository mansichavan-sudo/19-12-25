import pandas as pd

def build_product_features(queryset):
    rows = []
    for s in queryset:
        rows.append({
            "customer_id": s.customer_id,
            "product_id": s.product_id,
            "recency": s.recency_score,
            "frequency": s.frequency_score,
            "monetary": s.monetary_score,
        })
    return pd.DataFrame(rows)
