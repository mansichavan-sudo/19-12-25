FORBIDDEN_TRAINING_TABLES = {
    "pest_recommendations",
    "recommendation",
    "recommendationlog",
}

def assert_not_serving_data(queryset_or_model):
    name = (
        queryset_or_model._meta.db_table
        if hasattr(queryset_or_model, "_meta")
        else str(queryset_or_model)
    )
    if name in FORBIDDEN_TRAINING_TABLES:
        raise RuntimeError(
            f"🚨 DATA LEAKAGE BLOCKED: {name} cannot be used for training"
        )
