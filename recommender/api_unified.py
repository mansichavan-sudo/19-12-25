from django.http import JsonResponse 
from recommender.engine import UnifiedRecommender


def unified_recommendations(request, customer_id):

    try:
        customer_id = int(customer_id)
    except:
        return JsonResponse({"error": "Invalid customer ID"}, status=400)

    response = UnifiedRecommender.recommend(customer_id)

    return JsonResponse(response, safe=False)
