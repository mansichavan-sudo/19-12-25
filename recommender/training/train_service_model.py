# recommender/training/train_service_model.py

import pandas as pd
import joblib
from pathlib import Path

MODEL_DIR = Path("recommender/trained_models")
MODEL_DIR.mkdir(exist_ok=True)

SERVICE_MODEL_PATH = MODEL_DIR / "service_recommender.pkl"


def train_service_model(df: pd.DataFrame):
    """
    Simple frequency-based service recommender.
    """

    required_cols = {
        "customer_id",
        "service_id",
        "frequency",
        "monetary",
        "recency",
    }

    if df.empty or not required_cols.issubset(df.columns):
        raise Exception(
            f"❌ Service training DF missing columns: {required_cols - set(df.columns)}"
        )

    # Aggregate customer-service usage
    service_profile = (
        df.groupby(["customer_id", "service_id"])
        .agg(
            frequency=("frequency", "sum"),
            monetary=("monetary", "sum"),
            recency=("recency", "min"),
        )
        .reset_index()
    )

    joblib.dump(service_profile, SERVICE_MODEL_PATH)

    print(f"✅ Service model trained & saved → {SERVICE_MODEL_PATH}")
    return service_profile
