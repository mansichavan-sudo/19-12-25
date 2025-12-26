import logging
from engines import (
    collaborative_engine,
    cross_sell_engine,
    upsell_engine,
    demographic_engine,
)
from pipelines.persistence import persist

logger = logging.getLogger(__name__)

def recommend(customer_id: int, top_n: int = 10):
    # ---- HARD GUARDS ----
    assert isinstance(customer_id, int), "customer_id must be int"
    assert customer_id > 0, "invalid customer_id"

    logger.info("recommendation_started", extra={"customer_id": customer_id})

    candidates = []

    candidates += collaborative_engine.recommend(customer_id, top_n)
    candidates += cross_sell_engine.recommend(customer_id, top_n)
    candidates += upsell_engine.recommend(customer_id, top_n)
    candidates += demographic_engine.recommend(customer_id, top_n)

    if not candidates:
        logger.warning("no_candidates_generated", extra={"customer_id": customer_id})
        return []

    ranked = _rank_and_dedupe(candidates, top_n)

    persist(customer_id, ranked)

    logger.info(
        "recommendation_completed",
        extra={
            "customer_id": customer_id,
            "count": len(ranked)
        }
    )

    return ranked


def _rank_and_dedupe(candidates, top_n):
    best = {}

    for c in candidates:
        if c.product_id not in best or c.score > best[c.product_id].score:
            best[c.product_id] = c

    return sorted(best.values(), key=lambda x: x.score, reverse=True)[:top_n]
