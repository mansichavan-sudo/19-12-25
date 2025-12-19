from django.http import JsonResponse

def get_recommendations(request):
    return JsonResponse({"status": "ok", "data": []})



