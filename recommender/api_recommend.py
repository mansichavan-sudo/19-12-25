from django.http import JsonResponse
from .ml_service import get_recommendations_for_customer

def final_recommend_api(request, customer_id):
    try:
        result = get_recommendations_for_customer(customer_id)

        # If the ML function returns a LIST (correct behavior)
        if isinstance(result, list):
            return JsonResponse({
                "status": "success",
                "customer_id": customer_id,
                "count": len(result),
                "recommendations": result
            }, safe=False)

        # If it returns dict (fallback)
        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
