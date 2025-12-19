from crmapp.models import customer_details, Product
from .models import PestRecommendation


class DemographicRecommender:

    @staticmethod
    def recommend_for_customer(customer_id, limit=10):
        try:
            customer = customer_details.objects.get(id=customer_id)
        except customer_details.DoesNotExist:
            return {"status": "error", "message": "Customer not found"}

        city = customer.soldtopartycity
        state = customer.soldtopartystate
        postal = customer.soldtopartypostal

        # If no geographic data → return empty result
        if not city and not state and not postal:
            return {
                "status": "success",
                "city": None,
                "state": None,
                "postal_code": None,
                "total_products": 0,
                "recommended_products": []
            }

        # Dummy selection — future: filter by region
        products = Product.objects.all()[:limit]

        data = []
        for p in products:
            data.append({
                "product_id": p.product_id,
                "product_name": p.product_name,
                "score": 1.0,
                "method": "demographic",
                "matched_level": "city/state"
            })

        return {
            "status": "success",
            "city": city,
            "state": state,
            "postal_code": postal,
            "total_products": len(data),
            "recommended_products": data
        }


# ---------------------------------------------------------
# SAVE FUNCTION (CLEAN + INSERT)
# ---------------------------------------------------------
def save_demographic_recommendations(customer_id, products):

    # 1) Get customer
    try:
        customer = customer_details.objects.get(id=customer_id)
    except customer_details.DoesNotExist:
        return

    # 2) Remove OLD demographic rows for this customer
    PestRecommendation.objects.filter(
        customer_id=customer_id,
        recommendation_type="demographic"
    ).delete()

    rows = []

    # 3) Insert new rows
    for item in products:
        try:
            product = Product.objects.get(product_id=item["product_id"])
        except Product.DoesNotExist:
            continue

        rows.append(PestRecommendation(
            customer=customer,
            base_product=None,
            recommended_product=product,
            recommendation_type="demographic",  # normalized automatically
            confidence_score=item.get("score", 1.0)
        ))

    if rows:
        PestRecommendation.objects.bulk_create(rows)


# ---------------------------------------------------------
# PUBLIC WRAPPER
# ---------------------------------------------------------
def get_demographic_recommendations(customer_id, limit=5):

    result = DemographicRecommender.recommend_for_customer(customer_id, limit)

    if result["status"] == "success":
        products_to_save = [
            {
                "product_id": p["product_id"],
                "score": p["score"]
            }
            for p in result["recommended_products"]
        ]

        save_demographic_recommendations(customer_id, products_to_save)

    return result
