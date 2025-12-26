import pickle
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

def train_cf_model(df):
    pivot = df.pivot(
        index="customer_id",
        columns="product_id",
        values="frequency"
    ).fillna(0)

    similarity = cosine_similarity(pivot)

    model = {
        "matrix": pivot,
        "similarity": similarity,
    }

    with open("trained_models/cf_v1.pkl", "wb") as f:
        pickle.dump(model, f)
