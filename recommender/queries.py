
from django.db import connection

def fetch_recommendations(customer_id: int):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                pr.business_intent,
                pr.reco_channel,
                pr.confidence_score,
                pc.product_name,
                sc.service_name
            FROM pest_recommendations pr
            LEFT JOIN product_catalog pc
                ON pr.recommended_product_id = pc.product_id
            LEFT JOIN service_catalog sc
                ON pr.recommended_service_id = sc.service_id
            WHERE
                pr.customer_fk = %s
                AND pr.is_active = 1
                AND pr.serving_state = 'pending'
        """, [customer_id])

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]