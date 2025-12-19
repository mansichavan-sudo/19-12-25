from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import PestRecommendation
from crmapp.models import customer_details


@api_view(["GET"])
@permission_classes([AllowAny])
def get_pest_recommendations(request, customer_id):
    try:
        cust = customer_details.objects.get(id=customer_id)
    except customer_details.DoesNotExist:
        return Response({"status": "error", "message": "Customer not found"}, status=404)

    recs = PestRecommendation.objects.filter(customer=cust).select_related(
        "base_product", "recommended_product"
    ).order_by("-created_at")

    data = []
    for r in recs:
        data.append({
            "recommendation_type": r.recommendation_type,
            "confidence_score": float(r.confidence_score or 0),
            "base_product": r.base_product.product_name if r.base_product else None,
            "recommended_product": r.recommended_product.product_name if r.recommended_product else None,
            "created_at": r.created_at,
        })

    return Response({
        "status": "success",
        "customer_id": customer_id,
        "count": len(data),
        "recommendations": data
    })
