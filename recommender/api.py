from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .recommender_engine import get_recommendations


@csrf_exempt
def recommend_products(request):
    """
    API Endpoint: POST /recommend-products/
    Body: { "customer_id": "<customer primary key id>" }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST request required"}, status=400)

    try:
        body = json.loads(request.body.decode("utf-8"))

        # The API expects the REAL primary key "id" from crmapp_customer_details
        customer_id = body.get("customer_id")

        if customer_id is None:
            return JsonResponse({"error": "customer_id is required"}, status=400)

        # Validate number
        try:
            customer_id = int(customer_id)
        except:
            return JsonResponse({"error": "customer_id must be an integer"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)

    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=400)

    # 🔥 Call Recommendation Engine (returns dict)
    result = get_recommendations(customer_id)

    return JsonResponse(result, safe=False)
