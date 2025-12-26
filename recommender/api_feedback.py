from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json

from recommender.models import PestRecommendation


@require_POST
def recommendation_feedback(request):
    """
    Payload:
    {
        "recommendation_id": 4153,
        "action": "accepted" | "rejected"
    }
    """

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    rec_id = payload.get("recommendation_id")
    action = payload.get("action")

    if action not in ("accepted", "rejected"):
        return JsonResponse({"error": "Invalid action"}, status=400)

    rec = get_object_or_404(PestRecommendation, id=rec_id)

    # ---- STATE TRANSITION ----
    rec.action = action
    rec.serving_state = action
    rec.updated_at = timezone.now()

    rec.save(update_fields=["action", "serving_state", "updated_at"])

    return JsonResponse({
        "status": "ok",
        "recommendation_id": rec.id,
        "action": action
    })
