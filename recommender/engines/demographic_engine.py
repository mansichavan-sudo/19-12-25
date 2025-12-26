def demographic_recommendations(customer):
    results = []

    if customer.customer_type == "commercial":
        results.append({
            "product_id": 12,
            "score": 0.8,
            "method": "demographic",
            "reason": "Commercial customers often need fumigation"
        })

    return results
