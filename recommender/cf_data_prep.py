import pandas as pd
import numpy as np
from django.utils import timezone
from crmapp.models import PurchaseHistory
from sklearn.metrics.pairwise import cosine_similarity


# ----------------------------------------------------
# LOAD EVENTS FOR COLLABORATIVE FILTERING
# ----------------------------------------------------
def load_cf_events():
    qs = PurchaseHistory.objects.filter(
        product_id__isnull=False,
        purchase_type="PRODUCT"          # ✅ CRITICAL
    ).values(
        "customer_id",
        "product_id",
        "quantity",
        "total_amount",
        "purchased_at"
    )

    df = pd.DataFrame.from_records(qs)

    if df.empty:
        return df

    # -----------------------------
    # Time features
    # -----------------------------
    now = timezone.now()

    df["purchased_at"] = pd.to_datetime(df["purchased_at"], utc=True)
    df["days_ago"] = (now - df["purchased_at"]).dt.days.clip(lower=0)

    # Exponential time decay (30-day half-life)
    df["recency_weight"] = np.exp(-df["days_ago"] / 30.0)

    # -----------------------------
    # Numeric safety
    # -----------------------------
    df["quantity"] = df["quantity"].fillna(0).astype(float)
    df["total_amount"] = df["total_amount"].fillna(0).astype(float)

    df["qty_weight"] = np.log1p(df["quantity"])
    df["amt_weight"] = np.log1p(df["total_amount"])

    # -----------------------------
    # Final implicit interaction score
    # -----------------------------
    df["score"] = (
        1.0
        + df["qty_weight"]
        + df["amt_weight"]
    ) * df["recency_weight"]

    # Prevent extreme dominance
    df["score"] = df["score"].clip(upper=10.0)

    return df[["customer_id", "product_id", "score"]]


# ----------------------------------------------------
# USER–ITEM MATRIX
# ----------------------------------------------------
def build_user_item_matrix(df):
    return (
        df
        .groupby(["customer_id", "product_id"])["score"]
        .sum()
        .unstack(fill_value=0)
    )


# ----------------------------------------------------
# USER SIMILARITY
# ----------------------------------------------------
def compute_user_similarity(user_item_matrix):
    sim = cosine_similarity(user_item_matrix)
    return pd.DataFrame(
        sim,
        index=user_item_matrix.index,
        columns=user_item_matrix.index
    )
