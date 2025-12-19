# recommender/api_recommend.py

from django.http import JsonResponse
from django.db import connection
import pickle
import os
import json

MODEL_PATH = "recommender/trained_models/final_hybrid_model.pkl"


def final_recommend_api(request, customer_id):
    try:
        # -------------------------------------------------------
        # 1. LOAD AI MODEL 
        # -------------------------------------------------------
        if not os.path.exists(MODEL_PATH):
            return JsonResponse({"error": "AI model missing"}, status=404)

        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)

        # Collaborative Filtering Base Recommendations
        recommendations = model.get(customer_id, [])

        # -------------------------------------------------------
        # 2. FETCH CUSTOMER PROFILE / DEMOGRAPHICS
        # -------------------------------------------------------
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT fullname, primaryemail, primarycontact,
                       shifttopartyaddress, shifttopartycity, 
                       shifttopartystate, shifttopartypostal
                FROM crmapp_customer_details
                WHERE customerid = %s
            """, [customer_id])

            customer_row = cursor.fetchone()

        if not customer_row:
            return JsonResponse({"error": "Customer not found"}, status=404)

        customer_profile = {
            "name": customer_row[0],
            "email": customer_row[1],
            "phone": customer_row[2],
            "address": customer_row[3],
            "city": customer_row[4],
            "state": customer_row[5],
            "postal": customer_row[6],
        }

        # -------------------------------------------------------
        # 3. FETCH PURCHASE HISTORY 
        # -------------------------------------------------------
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT product_name, quantity, total_amount, invoice_type,
                       purchased_at
                FROM crmapp_purchasehistory
                WHERE customer_id = %s
                ORDER BY purchased_at DESC
            """, [customer_id])

            purchase_rows = cursor.fetchall()

        purchase_history = [
            {
                "product_name": row[0],
                "quantity": float(row[1]),
                "total_amount": float(row[2]),
                "invoice_type": row[3],
                "time": row[4].strftime("%Y-%m-%d %H:%M"),
            }
            for row in purchase_rows
        ]

        # -------------------------------------------------------
        # 4. UPSell Recommendation Logic
        # -------------------------------------------------------
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT product_id
                FROM crmapp_purchasehistory
                WHERE customer_id = %s
                ORDER BY purchased_at DESC
                LIMIT 1
            """, [customer_id])

            last_product = cursor.fetchone()

        upsell_list = []
        if last_product:
            last_pid = last_product[0]

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT product_name
                    FROM crmapp_product
                    WHERE product_id != %s
                    AND category = (
                        SELECT category FROM crmapp_product WHERE product_id = %s
                    )
                    LIMIT 5
                """, [last_pid, last_pid])

                upsell_list = [u[0] for u in cursor.fetchall()]

        # -------------------------------------------------------
        # 5. Cross-Sell Recommendation Logic
        # -------------------------------------------------------
        crosssell_list = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT p.category
                FROM crmapp_purchasehistory ph
                JOIN crmapp_product p ON ph.product_id = p.product_id
                WHERE ph.customer_id = %s
            """, [customer_id])

            categories = tuple([c[0] for c in cursor.fetchall()])

        if categories:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT product_name
                    FROM crmapp_product
                    WHERE category NOT IN %s
                    LIMIT 10
                """, [categories])

                crosssell_list = [c[0] for c in cursor.fetchall()]

        # -------------------------------------------------------
        # 6. FINAL JSON RESPONSE
        # -------------------------------------------------------
        return JsonResponse({
            "status": "success",
            "customer_profile": customer_profile,
            "purchase_history": purchase_history,
            "ai_recommendations": recommendations,
            "upsell": upsell_list,
            "crosssell": crosssell_list,
            "message": "AI recommendations generated successfully"
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
