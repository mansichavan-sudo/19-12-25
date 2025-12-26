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


from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from recommender.engine import get_recommendations


@api_view(["GET"])
def recommendation_api(request):
    """
    GET /api/recommendations/?customer_id=14&top_n=5
    """
    customer_id = request.GET.get("customer_id")
    top_n = int(request.GET.get("top_n", 5))

    if not customer_id:
        return Response(
            {"status": "error", "message": "customer_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        customer_id = int(customer_id)
    except ValueError:
        return Response(
            {"status": "error", "message": "customer_id must be an integer"},
            status=status.HTTP_400_BAD_REQUEST
        )

    result = get_recommendations(customer_id=customer_id, top_n=top_n)

    return Response(result, status=status.HTTP_200_OK)
