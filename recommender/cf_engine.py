# recommender/cf_engine.py

def cf_recommendations(customer_id, k=5):
    from recommender.load_model import load_cf_model

    model = load_cf_model()
    if model is None:
        return []

    user_item = model["user_item_matrix"]
    similarity = model["similarity_df"]

    if customer_id not in similarity.index:
        return []

    # Similar users
    sim_scores = similarity.loc[customer_id].drop(customer_id)
    similar_users = sim_scores[sim_scores > 0].sort_values(ascending=False)

    if similar_users.empty:
        return []

    # Weighted product scores
    scores = user_item.loc[similar_users.index].T.dot(similar_users)

    # Remove already purchased
    purchased = user_item.loc[customer_id]
    scores = scores[purchased == 0]

    return [
        {"product_id": int(pid), "score": float(score)}
        for pid, score in scores.sort_values(ascending=False).head(k).items()
    ]
