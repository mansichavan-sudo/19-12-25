from django.contrib import admin
from .models import Item, Rating, SavedModel, Interaction, PestRecommendation
from crmapp.models import SentMessageLog, PurchaseHistory  # CRM models


# -----------------------------
# RECOMMENDER APP MODELS
# -----------------------------
admin.site.register(Item)
admin.site.register(Rating)
admin.site.register(SavedModel)
admin.site.register(Interaction)
admin.site.register(PestRecommendation)


# -----------------------------
# PURCHASE HISTORY ADMIN
# -----------------------------
@admin.register(PurchaseHistory) 

class PurchaseHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",           # FK to customer_details
        "invoice_type",
        "product_name",       # show unified product name
        "quantity",
        "total_amount",
        "purchased_at",
    )

    list_filter = ("invoice_type", "customer")

    search_fields = (
        "customer__fullname",
        "product_name",
    )
