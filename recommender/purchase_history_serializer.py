from rest_framework import serializers
from crmapp.models import PurchaseHistory

class PurchaseHistorySerializer(serializers.ModelSerializer):
    product_title = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseHistory
        fields = [
            "id",
            "invoice_type",
            "product_title",
            "quantity",
            "total_amount",
            "purchased_at",
        ]

    def get_product_title(self, obj):
        if obj.product:             # NORMAL INVOICE
            return obj.product.product_name
        return obj.product_name     # TAX INVOICE fallback
