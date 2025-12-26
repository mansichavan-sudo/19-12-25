from django.utils.timezone import now
import uuid
from recommender.models import PestRecommendation
from django.http import JsonResponse


def get_customer_recommendations(request, customer_id):
    recos = PestRecommendation.objects.filter(
        customer_fk=customer_id,
        serving_state='served'
    )[:5]

    recos.update(
        exposed_at=now(),
        exposure_channel='crm',
        exposure_id=uuid.uuid4().hex,
        serving_state='exposed'
    )

    return JsonResponse(list(recos.values()), safe=False)
