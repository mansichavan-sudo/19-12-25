import pickle
from datetime import datetime

def save_hybrid_model(model):
    version = datetime.now().strftime("%Y%m%d_%H%M")
    path = f"trained_models/hybrid_{version}.pkl"

    with open(path, "wb") as f:
        pickle.dump(model, f)

    return version
