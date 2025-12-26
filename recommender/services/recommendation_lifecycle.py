# services/recommendation_lifecycle.py

from django.db import transaction
from models import RecommendationServing, RecommendationEvent

@transaction.atomic
def mark_served(reco: RecommendationServing, metadata=None):
    if reco.state != "pending":
        return

    reco.state = "served"
    reco.save(update_fields=["state"])

    RecommendationEvent.objects.create(
        recommendation=reco,
        event_type="shown",
        metadata=metadata or {}
    )


@transaction.atomic
def mark_accepted(reco: RecommendationServing, metadata=None):
    if reco.state != "served":
        return

    reco.state = "accepted"
    reco.save(update_fields=["state"])

    RecommendationEvent.objects.create(
        recommendation=reco,
        event_type="accepted",
        metadata=metadata or {}
    )


@transaction.atomic
def mark_rejected(reco: RecommendationServing, metadata=None):
    if reco.state != "served":
        return

    reco.state = "rejected"
    reco.save(update_fields=["state"])

    RecommendationEvent.objects.create(
        recommendation=reco,
        event_type="rejected",
        metadata=metadata or {}
    )
