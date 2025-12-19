from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from crmapp.models import PurchaseHistory  # 👈 REQUIRED IMPORT
from datetime import datetime


@api_view(["GET"])
@permission_classes([AllowAny])   # ✔ Fixes 403 Forbidden
def get_purchase_history(request, customer_id):

    # Validate customer id
    try:
        customer_id = int(customer_id)
    except:
        return Response({
            "status": "error",
            "message": "Invalid customer ID"
        }, status=400)

    # Fetch data
    history = PurchaseHistory.objects.filter(
        customer_id=customer_id
    ).order_by("-purchased_at")

    result = []

    for item in history:
        result.append({
            "product": item.product.product_name if item.product else item.product_name,
            "quantity": float(item.quantity),
            "total_amount": float(item.total_amount),
            "invoice_type": item.invoice_type,
            "purchased_at": item.purchased_at.strftime("%Y-%m-%d %H:%M:%S"),  # ✔ Fix datetime serialization
        })

    return Response({
        "status": "success",
        "customer_id": customer_id,
        "count": len(result),
        "history": result
    })
