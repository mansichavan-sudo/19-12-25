def precision_at_k(recommended, actual, k=5):
    return len(set(recommended[:k]) & set(actual)) / k
