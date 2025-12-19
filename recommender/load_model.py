import os
import pickle
import joblib   # ← REQUIRED for .pkl models saved using joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "trained_models", "recommender_similarity.pkl")


def load_recommender_model():
    print("📥 Loading model from:", MODEL_PATH)

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"❌ Model missing at: {MODEL_PATH}")

    try:
        # Try loading using joblib
        model = joblib.load(MODEL_PATH)
        print("✅ Model loaded using joblib")
        return model

    except Exception as e:
        print("⚠️ Joblib failed, trying pickle:", e)

        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            print("✅ Model loaded using pickle")
            return model

        except Exception as e2:
            print("❌ ERROR: Model cannot be loaded with joblib or pickle")
            print("Error details:", e2)
            raise e2
 
 