from crmapp.models import customer_details, Product
from recommender.models import PestRecommendation
from django.db.models import Q


# ----------------------------------------------------------------------------------
# SCORING RULES (Based on fields that actually exist in your MySQL schema)
# ----------------------------------------------------------------------------------

def score_demographic_match(customer, product):

    score = 0
    total = 3   # number of demographic factors used

    # 1. REGION → PRODUCT CATEGORY match
    if customer.soldtopartystate:
        state = customer.soldtopartystate.lower()

        # Example: In some states fungicides sell more
        if "maharashtra" in state and "fungicide" in product.category.lower():
            score += 1

        if "gujarat" in state and "insecticide" in product.category.lower():
            score += 1

        if "karnataka" in state and "fertilizer" in product.category.lower():
            score += 1

    # 2. CITY → PRODUCT CATEGORY match
    if customer.soldtopartycity:
        city = customer.soldtopartycity.lower()

        if "pune" in city and "biopesticide" in product.category.lower():
            score += 1

        if "surat" in city and "insecticide" in product.category.lower():
            score += 1

    # 3. CUSTOMER TYPE → PRODUCT CATEGORY
    if customer.customer_type:
        ctype = customer.customer_type.lower()

        if "farmer" in ctype and "fertilizer" in product.category.lower():
            score += 1

        if "retailer" in ctype and "insecticide" in product.category.lower():
            score += 1

        if "distributor" in ctype and "herbicide" in product.category.lower():
            score += 1

    return round(score / total, 2)  # normalize to 0–1 score


# ----------------------------------------------------------------------------------
# MAIN FUNCTION
# ----------------------------------------------------------------------------------

def get_demographic_recommendations(customer_id):

    try:
        customer = customer_details.objects.get(id=customer_id)
    except customer_details.DoesNotExist:
        return []

    products = Product.objects.all()

    recommendations = []

    for product in products:
        score = score_demographic_match(customer, product)

        if score >= 0.30:  # minimum 30% relevance
            recommendations.append({
                "product_id": product.product_id,
                "product_name": product.product_name,
                "category": product.category,
                "score": score
            })

    # sort by score
    recommendations.sort(key=lambda x: x["score"], reverse=True)

    # save top 5 to DB for dashboard
    for item in recommendations[:5]:
        PestRecommendation.objects.update_or_create(
            customer_id=customer_id,
            recommended_product_id=item["product_id"],
            recommendation_type="demographic",
            defaults={"confidence_score": item["score"] * 100}
        )

    return recommendations[:5]
