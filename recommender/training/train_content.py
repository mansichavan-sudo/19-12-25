from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import pickle

def train_content_model(df):
    features = df[["recency", "frequency", "monetary"]]

    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    nn = NearestNeighbors(n_neighbors=10)
    nn.fit(X)

    model = {
        "scaler": scaler,
        "nn": nn,
    }

    with open("trained_models/content_v1.pkl", "wb") as f:
        pickle.dump(model, f)
