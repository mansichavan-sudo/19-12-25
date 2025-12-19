from django.http import JsonResponse
from crmapp.models import customer_details
from recommender.demographic_service import DemographicRecommender


def demographic_recommendations(request, customer_id):

    # --- Validate ---
    try:
        customer_id = int(customer_id)
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid customer ID",
            "city": "",
            "state": "",
            "postal_code": "",
            "recommended_products": []
        }, status=400)

    # --- Fetch customer address details ---
    customer = customer_details.objects.filter(id=customer_id).first()
    if not customer:
        return JsonResponse({
            "status": "error",
            "message": "Customer not found",
            "city": "",
            "state": "",
            "postal_code": "",
            "recommended_products": []
        }, status=404)

    city = customer.soldtopartycity or ""
    state = customer.soldtopartystate or ""
    postal = customer.soldtopartypostal or ""

    # --- Call your demographic engine ---
    result = DemographicRecommender.recommend_for_customer(customer_id)

    # Ensure consistent structure
    return JsonResponse({
        "status": "success",
        "message": "Demographic recommendations generated",
        "city": city,
        "state": state,
        "postal_code": postal,
        "recommended_products": result.get("recommended_products", []),
    })
