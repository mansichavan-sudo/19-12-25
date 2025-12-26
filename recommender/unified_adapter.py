def normalize_output(
    *,
    item_id,
    score,
    method,
    intent,
    explanation,
    channel
):
    return {
        "item_id": item_id,
        "final_score": round(float(score), 3),
        "algorithm_strategy": method,        # collaborative / content / rule_based
        "recommendation_type": intent,        # upsell / crosssell / retention
        "explanation": explanation,
        "reco_channel": channel               # product / service
    }
