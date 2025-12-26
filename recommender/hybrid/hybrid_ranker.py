WEIGHTS = {
    "cf": 0.35,
    "content": 0.25,
    "cross_sell": 0.2,
    "upsell": 0.1,
    "demographic": 0.1
}

def hybrid_rank(candidates, top_n=10):
    scores = {}

    for c in candidates:
        pid = c["product_id"]
        weighted = c["score"] * WEIGHTS[c["method"]]

        if pid not in scores:
            scores[pid] = {"score": 0, "reason": []}

        scores[pid]["score"] += weighted
        scores[pid]["reason"].append(c["reason"])

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    return [
        {
            "product_id": pid,
            "score": round(meta["score"], 4),
            "reason": " | ".join(set(meta["reason"]))
        }
        for pid, meta in ranked[:top_n]
    ]
