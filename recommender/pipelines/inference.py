from recommender.engines import (
    collaborative,
    content_based,
    upsell,
    cross_sell,
    demographic,
)
from recommender.pipelines.persistence import persist_recommendations
from recommender.pipelines.fallback import fallback_if_empty


def recommend(customer_id, top_k=10):
    """
    FINAL production recommendation entrypoint
    """

    candidates = []

    candidates += collaborative.recommend(customer_id)
    candidates += content_based.recommend(customer_id)
    candidates += upsell.recommend(customer_id)
    candidates += cross_sell.recommend(customer_id)
    candidates += demographic.recommend(customer_id)

    ranked = _rank_and_dedupe(candidates, top_k)
    ranked = fallback_if_empty(customer_id, ranked)

    persist_recommendations(customer_id, ranked)
    return ranked


def _rank_and_dedupe(candidates, top_k):
    seen = {}
    for c in candidates:
        pid = c["product_id"]
        if pid not in seen or c["score"] > seen[pid]["score"]:
            seen[pid] = c

    ranked = sorted(
        seen.values(),
        key=lambda x: (-x["score"], x.get("priority", 100))
    )

    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked[:top_k]
