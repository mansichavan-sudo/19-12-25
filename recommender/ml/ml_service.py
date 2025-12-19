# recommender/ml/ml_service.py

import threading
from .recommender_engine import load_model, recommend_products

# Prevent multiple loads in Django autoreload environment
_model_cache = {
    "model": None,
    "loaded": False,
    "lock": threading.Lock()
}


def get_model():
    """
    Safely load the model once and cache it in memory.
    Prevents repeated pickle loading after every API request.
    """
    if _model_cache["loaded"]:
        return _model_cache["model"]

    with _model_cache["lock"]:
        if not _model_cache["loaded"]:
            try:
                _model_cache["model"] = load_model()
                _model_cache["loaded"] = True
            except Exception as e:
                raise RuntimeError(f"Failed to load ML model: {str(e)}")

    return _model_cache["model"]


def get_recommendations(customer_id, top_n=5):
    """
    Wrapper used by Django views.
    Ensures model is loaded and returns clean response.
    """

    # Ensure model is loaded first
    try:
        get_model()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Model load failed: {str(e)}",
            "recommendations": []
        }

    # Use recommender_engine logic
    result = recommend_products(customer_id, top_n=top_n)
    return result
