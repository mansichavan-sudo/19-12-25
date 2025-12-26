from django.db.models.signals import post_save
from django.dispatch import receiver
from crmapp.models import PurchaseHistory
from recommender.models import PestRecommendation

@receiver(post_save, sender=PurchaseHistory)
def link_recommendation_conversion(sender, instance, created, **kwargs):
    if not created:
        return

    rec = (
        PestRecommendation.objects
        .filter(
            external_customer_id=instance.customer_id,
            recommended_product_id=instance.product_id,
            serving_state='accepted',
            converted_at__isnull=True,
            served_at__lte=instance.purchased_at
        )
        .order_by('-served_at')
        .first()
    )

    if rec:
        rec.converted_at = instance.purchased_at
        rec.converted_product_id = instance.product_id
        rec.revenue_amount = instance.total_amount
        rec.save(update_fields=[
            'converted_at',
            'converted_product',
            'revenue_amount'
        ])
