# recommender/services/serving.py
from django.utils import timezone
from recommender.models import PestRecommendation

def mark_served(reco_id):
    PestRecommendation.objects.filter(
        id=reco_id,
        serving_state="pending"
    ).update(
        serving_state="served",
        served_at=timezone.now()
    )
