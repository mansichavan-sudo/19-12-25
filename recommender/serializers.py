from rest_framework import serializers
from crmapp.models import PurchaseHistory, customer_details, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "product_name"]


class CustomerMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = customer_details
        fields = ["id", "fullname", "primarycontact"]


class PurchaseHistorySerializer(serializers.ModelSerializer):
    """
    Serializer that correctly handles:
    - product FK OR product_name string (tax invoice)
    - invoice_id or tax_invoice_id
    - customer PK
    """

    product = ProductSerializer(read_only=True)
    customer = CustomerMiniSerializer(read_only=True)

    class Meta:
        model = PurchaseHistory
        fields = [
            "id",
            "product",          # FK (NULL for tax invoice)
            "product_name",     # string when FK not available
            "quantity",
            "total_amount",
            "invoice_type",
            "purchased_at",
            "customer",         # FK
            "invoice_id",
            "tax_invoice_id",
        ]
