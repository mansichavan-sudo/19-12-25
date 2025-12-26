import pandas as pd
import numpy as np
from recommender.recommender_engine import recommend_cf
from recommender.cf_data_prep import load_cf_events
from collections import defaultdict


def train_test_split(df, test_days=30):
    """
    Split by time:
    - Train: older purchases
    - Test: recent purchases
    """
    cutoff = df["purchased_at"].max() - pd.Timedelta(days=test_days)
    train = df[df["purchased_at"] <= cutoff]
    test = df[df["purchased_at"] > cutoff]
    return train, test


def evaluate_cf(k=5):
    df = load_cf_events()

    if df.empty:
        print("❌ No data for evaluation")
        return

    # Reload raw events including time
    from crmapp.models import PurchaseHistory
    raw = pd.DataFrame.from_records(
        PurchaseHistory.objects.filter(
            product_id__isnull=False,
            purchase_type="PRODUCT"
        ).values("customer_id", "product_id", "purchased_at")
    )

    raw["purchased_at"] = pd.to_datetime(raw["purchased_at"], utc=True)

    train_df, test_df = train_test_split(raw)

    # Ground truth: future purchases
    true_items = (
        test_df
        .groupby("customer_id")["product_id"]
        .apply(set)
        .to_dict()
    )

    precision, recall, hits = [], [], []

    for customer_id, actual_items in true_items.items():
        recs = recommend_cf(customer_id, top_n=k)
        rec_items = {r["product_id"] for r in recs}

        if not rec_items:
            continue

        intersection = rec_items & actual_items

        precision.append(len(intersection) / k)
        recall.append(len(intersection) / len(actual_items))
        hits.append(1 if intersection else 0)

    print("📊 CF Evaluation Results")
    print(f"Precision@{k}: {np.mean(precision):.3f}")
    print(f"Recall@{k}:    {np.mean(recall):.3f}")
    print(f"HitRate@{k}:   {np.mean(hits):.3f}")
