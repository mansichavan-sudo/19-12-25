# recommender/views.py

from django.shortcuts import render
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import ensure_csrf_cookie
from .rapbooster_api import send_email_message 
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
import json
import pickle
import os
import requests
import re
from .rapbooster_api import send_whatsapp_message, send_email_message, send_recommendation_message
from django.shortcuts import get_object_or_404
# Models
from crmapp.models import MessageTemplates, Product, customer_details ,PurchaseHistory,ServiceProduct,invoice 
from .models import Item, Rating, PestRecommendation
from django.http import HttpResponse
from openpyxl import Workbook
import csv
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from crmapp.models import SentMessageLog
from django.db import connection
from .engine import get_recommendations
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST,require_GET
import json
import os
import re
import requests
from django.shortcuts import get_object_or_404
from crmapp.models import customer_details, MessageTemplates, SentMessageLog , CustomerContract
from .ml_service import get_recommendations_for_customer
import traceback
 




# Recommender Engine
from .recommender_engine import (
    get_content_based_recommendations,
    get_collaborative_recommendations,
    get_upsell_recommendations,
    get_crosssell_recommendations,
    generate_recommendations_for_user,
    get_user_based_recommendations
)

from .utils import send_recommendation_message
import joblib


# -------------------------------------------------------------
#  Load ML Models
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CF = os.path.join(BASE_DIR, "trained_models", "recommender_model.pkl")
MODEL_HYBRID = os.path.join(BASE_DIR, "trained_models", "hybrid_model.pkl")

cf_model = joblib.load(MODEL_CF) if os.path.exists(MODEL_CF) else None
hybrid_model = joblib.load(MODEL_HYBRID) if os.path.exists(MODEL_HYBRID) else None


# Helper: Render placeholders
def render_template(text, data):
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", lambda m: str(data.get(m.group(1), "")), text or "")

# ============================================================
# 1️⃣ RECOMMENDATION UI
# ============================================================
@login_required
@ensure_csrf_cookie
def recommendation_ui(request):
    """
    Renders the single-page UI merging Content-Based + Personalized into one.
    Template will populate customers, templates; the rest is done with AJAX.
    """
    # Load customers minimally (id + fullname) for dropdowns
    customers = customer_details.objects.all().values("id", "fullname")
    # Load templates active by default; when customer selected front-end will pick up customer-specific filtering by reloading templates if needed
    templates = MessageTemplates.objects.filter(is_active=True).order_by("category", "message_type")
    return render(request, 'recommender/recommendations_ui.html', {
        'templates': templates,
        'customers': customers,
    })

# ============================================================
# 2️⃣ CONTENT-BASED RECOMMENDATIONS (product → product)
# ============================================================
def recommendations_view(request):
    product_name = request.GET.get('product')
    if not product_name:
        return JsonResponse({'error': 'Please provide a product name.'}, status=400)
    try:
        results = get_content_based_recommendations(product_name)
        return JsonResponse({'recommended_products': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ============================================================
# 3️⃣ COLLABORATIVE FILTERING (customer → customer)
# ============================================================
def collaborative_view(request, customer_id):
    try:
        results = get_collaborative_recommendations(customer_id)
        return JsonResponse({'similar_customers': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
 

from django.db.models import Count,Avg

from django.http import JsonResponse


from django.http import JsonResponse
from django.db.models import Avg, Count, DecimalField
from django.db.models.functions import Coalesce
from .recommender_engine import get_upsell_recommendations
from django.http import JsonResponse
from django.db.models import Count, Avg
from django.db.models.functions import Coalesce
from decimal import Decimal
from crmapp.models import Product, ServiceProduct


def popular_products_api(request, customer_id):
    products = Product.objects.annotate(
        sales=Count('purchasehistory'),
        avg_price=Coalesce(
            Avg('serviceproduct__price'),
            Decimal('0.00')
        )
    ).order_by('-sales')[:5]

    result = [
        {
            "product_name": p.product_name,
            "average_price": float(round(p.avg_price, 2)),
            "reason": "Popular product"
        }
        for p in products
    ]

    return JsonResponse(result, safe=False)


# -------------------------
# Upsell Suggestions API
# ------------------------- 
from django.http import JsonResponse
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.db.models import Max, Avg, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.db.models import Avg, Max, DecimalField
from django.db.models.functions import Coalesce
from crmapp.models import customer_details, ServiceProduct
from recommender.models import PestRecommendation
 


def upsell_view(request, customer_id):
    """
    customer_id here = customerid (e.g. UDAKAL4374)
    """

    # 🔹 STEP 1: Resolve customerid → BIGINT id
    try:
        customer = customer_details.objects.get(customerid=customer_id)
    except customer_details.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Customer not found"
        }, status=404)

    # ===============================
    # ---------- PRODUCTS ----------
    # ===============================
    product_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,             # ✅ FIX
            recommendation_type="upsell",
            recommended_product__isnull=False
        )
        .values(
            "recommended_product__product_id",
            "recommended_product__product_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:7]
    )

    products = []
    for p in product_qs:
        avg_price = (
            ServiceProduct.objects
            .filter(product_id=p["recommended_product__product_id"])
            .aggregate(
                avg=Coalesce(
                    Avg("price"),
                    0,
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )["avg"]
        )

        products.append({
            "id": p["recommended_product__product_id"],
            "name": p["recommended_product__product_name"],
            "confidence": float(p["confidence"]),
            "average_price": float(round(avg_price, 2))
        })

    # ===============================
    # ---------- SERVICES ----------
    # ===============================
    service_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,             # ✅ FIX
            recommendation_type="upsell",
            recommended_service__isnull=False
        )
        .values(
            "recommended_service__service_id",
            "recommended_service__service_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:3]
    )

    services = [
        {
            "id": s["recommended_service__service_id"],
            "name": s["recommended_service__service_name"],
            "confidence": float(s["confidence"])
        }
        for s in service_qs
    ]

    return JsonResponse({
        "status": "success",
        "products": products,
        "services": services
    })

from django.http import JsonResponse
from django.db.models import Max
from django.shortcuts import get_object_or_404
from crmapp.models import customer_details 
from .models import PestRecommendation


def crosssell_view(request, customer_id):
    customer = customer_details.objects.get(customerid=customer_id)

    product_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="crosssell",
            recommended_product__isnull=False
        )
        .values(
            "recommended_product__product_id",
            "recommended_product__product_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:7]
    )

    products = [
        {
            "id": p["recommended_product__product_id"],
            "name": p["recommended_product__product_name"],
            "confidence": float(p["confidence"])
        }
        for p in product_qs
    ]

    service_qs = (
        PestRecommendation.objects
        .filter(
            customer=customer,
            recommendation_type="crosssell",
            recommended_service__isnull=False
        )
        .values(
            "recommended_service__service_id",
            "recommended_service__service_name"
        )
        .annotate(confidence=Max("confidence_score"))
        .order_by("-confidence")[:3]
    )

    services = [
        {
            "id": s["recommended_service__service_id"],
            "name": s["recommended_service__service_name"],
            "confidence": float(s["confidence"])
        }
        for s in service_qs
    ]

    return JsonResponse({
        "status": "success",
        "products": products,
        "services": services
    })


# ============================================================
# 6️⃣ FINAL DASHBOARD TABLE (CRM)
# ============================================================ 
from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import render


def recommendation_dashboard(request):
    filter_type = (request.GET.get("type") or "").strip().lower()
    search = (request.GET.get("search") or "").strip()

    sql = """
        SELECT
            pr.id,
            pr.customer_id,
            c.fullname,
            c.primarycontact,
            c.primaryemail,

            CONCAT_WS(', ',
                c.soldtopartyaddress,
                c.soldtopartycity,
                c.soldtopartystate,
                c.soldtopartypostal
            ) AS address,

            lp.product_name AS purchase_product,
            sp.quantity,
            sp.price,
            sm.service_date,

            rp.product_name AS recommended_product,
            sc.service_name AS recommended_service,

            COALESCE(rp.category, sc.service_category) AS category,
            pr.recommendation_type,
            pr.confidence_score

        FROM pest_recommendations pr

        LEFT JOIN crmapp_customer_details c
            ON c.id = pr.customer_id

        LEFT JOIN crmapp_service_management sm
            ON sm.id = (
                SELECT id
                FROM crmapp_service_management
                WHERE customer_id = c.id
                ORDER BY service_date DESC
                LIMIT 1
            )

        LEFT JOIN crmapp_serviceproduct sp
            ON sp.id = (
                SELECT id
                FROM crmapp_serviceproduct
                WHERE service_id = sm.id
                ORDER BY id DESC
                LIMIT 1
            )

        LEFT JOIN crmapp_product lp
            ON lp.product_id = sp.product_id

        LEFT JOIN crmapp_product rp
            ON rp.product_id = pr.recommended_product_id

        LEFT JOIN service_catalog sc
            ON sc.service_id = pr.recommended_service_id

        WHERE 1 = 1
    """

    params = []

    if filter_type:
        sql += " AND pr.recommendation_type = %s"
        params.append(filter_type)

    if search:
        sql += """
            AND (
                c.fullname LIKE %s
                OR lp.product_name LIKE %s
                OR rp.product_name LIKE %s
                OR sc.service_name LIKE %s
            )
        """
        like = f"%{search}%"
        params.extend([like, like, like, like])

    sql += " ORDER BY pr.confidence_score DESC, sm.service_date DESC"

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    recommendations = [{
        "customer_id": r[1],
        "customer_name": r[2],
        "phone": r[3],
        "email": r[4],
        "address": r[5] or "—",

        "purchase_product": r[6] or "—",
        "quantity": r[7] or "—",
        "price": float(r[8]) if r[8] else "—",
        "purchase_date": r[9],

        "recommended_product": r[10] or "—",
        "recommended_service": r[11] or "—",

        "category": r[12] or "—",
        "recommendation_type": r[13],
        "confidence_score": float(r[14]) if r[14] else 0,
    } for r in rows]

    paginator = Paginator(recommendations, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "recommender/recommendation_dashboard.html", {
        "page_obj": page_obj,
        "recommendations": page_obj,   # IMPORTANT
        "filter_type": filter_type,
        "search": search,
    })

# ============================================================
# 7️⃣ GET ALL PRODUCTS
# ============================================================
def get_all_products(request):
    try:
        products = list(Product.objects.values_list("product_name", flat=True))
        return JsonResponse({'products': products})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


import logging
logger = logging.getLogger(__name__)

@login_required
@require_GET
def api_ai_personalized(request, customer_id):
    """
    Returns AI personalized recommendations for a customer.
    URL sends REAL PK <int:customer_id>.
    """

    # ----------------------------------------------------------------------
    # 1. Validate & fetch customer (using REAL primary key)
    # ----------------------------------------------------------------------
    try:
        customer_id = int(customer_id)
    except ValueError:
        return JsonResponse({"error": "Invalid customer ID"}, status=400)

    customer = get_object_or_404(customer_details, id=customer_id)

    # ----------------------------------------------------------------------
    # 2. Generate recommendations
    # ----------------------------------------------------------------------
    try:
        recs = generate_recommendations_for_user(
            customer_id=customer_id,
            top_n=10
        )
    except Exception as e:
        logger.error(f"[AI] Recommendation generation failed for customer {customer_id}: {e}")
        recs = []

    # ----------------------------------------------------------------------
    # 3. Normalize recommendation objects → clean JSON list
    # ----------------------------------------------------------------------
    final_recs = []

    for r in recs:
        try:
            product_id = (
                getattr(r, "product_id", None)
                or getattr(r, "id", None)
            )

            title = (
                getattr(r, "title", None)
                or getattr(r, "product_name", None)
                or "Unknown Item"
            )

            final_recs.append({
                "product_id": product_id,
                "product": title,   # UI friendly
                "title": title,
                "category": getattr(r, "category", None),
                "tags": getattr(r, "tags", None),
                "confidence_score": getattr(r, "score", None),
     })

        except Exception as e:
            logger.warning(f"[AI] Failed to normalize recommendation: {e}")
            continue

    # ----------------------------------------------------------------------
    # 4. JSON Response
    # ----------------------------------------------------------------------
    return JsonResponse({
        "customer_id": customer.id,
        "customer_name": customer.fullname,
        "recommendations": final_recs,
    })

# ============================================================
# 9️⃣ AUTOMATIC MESSAGE GENERATION + SEND
# ============================================================
@csrf_exempt
def generate_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)

        customer = data.get("customer_name")
        base = data.get("base_product")
        rec = data.get("recommended_product")
        rec_type = data.get("recommendation_type")
        phone_number = data.get("phone_number")

        if not all([customer, base, rec, rec_type, phone_number]):
            return JsonResponse({"error": "Missing fields"}, status=400)

        message = (
            f"Hello {customer}, we recommend trying our {rec} as a perfect "
            f"{rec_type.lower()} option with your {base}. "
            f"It ensures better pest control results! 🌾🛡️"
        )

        from .rapbooster_api import send_recommendation_message

        status_code, api_response = send_recommendation_message(
            phone_number=phone_number,
            message=message,
            customer_name=customer
        )

        return JsonResponse({
            "customer": customer,
            "phone": phone_number,
            "message": message,
            "status": "sent" if status_code == 200 else "failed",
            "api_response": api_response
        })

    except Exception as e:
        logger.error(f"Message generation error: {e}")
        return JsonResponse({"error": str(e)}, status=500)



# ============================================================
# 🔟 RAP BOOSTER MESSAGE SENDER (FINAL FIXED VERSION)
# ============================================================
@csrf_exempt
def send_message_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        # ENV fallback
        RAPBOOSTER_API_KEY = os.getenv("RAPBOOSTER_API_KEY")
        if not RAPBOOSTER_API_KEY:
            RAPBOOSTER_API_KEY = "6538c8eff027d41e9151"  # Safe fallback

        RAPBOOSTER_SEND_URL = "https://rapbooster.in/api/v1/sendMessage"

        data = json.loads(request.body)
        template_id = data.get("template_id")
        customer_id = data.get("customer_id")

        if not template_id or not customer_id:
            return JsonResponse({"error": "template_id and customer_id are required"}, status=400)

        template = MessageTemplates.objects.get(id=template_id)
        customer = customer_details.objects.get(id=customer_id)

        phone = str(customer.primarycontact).strip()

        # Phone validation: 10–15 digits
        if not re.fullmatch(r"\+?\d{10,15}", phone):
            return JsonResponse({"error": "Invalid phone number format"}, status=400)

        # Render the template body
        rendered_body = render_template(template.body, {
            "customer_name": customer.fullname,
            "recommended_product": data.get("recommended_product", "")
        })

        payload = {
            "apikey": RAPBOOSTER_API_KEY,
            "phone": phone,
            "message": rendered_body
        }

        response = requests.post(RAPBOOSTER_SEND_URL, json=payload, timeout=10)

        try:
            resp_json = response.json()
        except:
            resp_json = {}

        # Success check
        success = response.status_code == 200 and resp_json.get("status") == "success"

        SentMessageLog.objects.create(
            template=template,
            recipient=phone,
            channel=template.message_type,
            rendered_body=rendered_body,
            status="success" if success else "failed",
            provider_response=response.text,
        )

        if success:
            return JsonResponse({
                "status": "success",
                "message_id": resp_json.get("message_id"),
                "phone": resp_json.get("phone")
            })

        return JsonResponse({
            "status": "failed",
            "error": resp_json.get("error", "Unknown error"),
            "http_status": response.status_code
        }, status=500)

    except MessageTemplates.DoesNotExist:
        return JsonResponse({"error": "Template not found"}, status=404)

    except customer_details.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    except requests.RequestException as e:
        logger.error(f"RapBooster error: {e}")
        return JsonResponse({"error": "Network error contacting RapBooster"}, status=500)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)
    


# ------------------------------------------------------------
# API → Load customer details, purchase history & AI product
# ------------------------------------------------------------ 

# ============================================================
# 1️⃣1️⃣ FIXED – GET CUSTOMER FULL DATA
# ============================================================ 
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from crmapp.models import customer_details, PurchaseHistory

def get_customer_data(request, customer_id):

    customer = get_object_or_404(customer_details, customerid=customer_id)

    # phone
    phone = customer.primarycontact or customer.secondarycontact or ""

    # address formatting
    address = f"{customer.soldtopartyaddress}, {customer.soldtopartycity}, {customer.soldtopartystate}, {customer.soldtopartypostal}"

    # purchase history
    purchases = PurchaseHistory.objects.filter(customer_id=customer_id).order_by("-purchased_at")

    purchase_rows = []
    last_purchase_date = None
    last_purchase_item = None

    for p in purchases:

        if last_purchase_date is None:
            last_purchase_date = p.purchased_at.strftime("%Y-%m-%d %H:%M")
            last_purchase_item = p.product_name

        purchase_rows.append({
            "product_name": p.product_name,
            "quantity": float(p.quantity),
            "date": p.purchased_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({
        "customer": {
            "id": customer.customerid,
            "name": customer.fullname,
            "phone": phone,
            "address": address,
            "last_purchase": last_purchase_date,
            "last_purchase_item": last_purchase_item,
        },
        "purchase_history": purchase_rows,
        "recommendations": []
    })

# ============================================================
# 1️⃣1️⃣ CUSTOMER RECOMMENDATIONS API
# ============================================================  
def customer_recommendations_api(request, customer_id):
    try:
        # Get list of recommended products
        recommendations = get_user_based_recommendations(customer_id)

        # Select the top recommendation (or fallback)
        if recommendations and len(recommendations) > 0:
            top_recommendation = recommendations[0]
        else:
            top_recommendation = "General Pest Control"  # fallback

        # Send response in UI expected format
        return JsonResponse({
            "customer_id": customer_id,
            "recommended_product": top_recommendation
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# api/customers/

# ----------- FETCH ALL CUSTOMERS ----------- 
from crmapp.models import customer_details, PurchaseHistory
from django.db.models import Max
def get_all_customers(request):

    customers = list(customer_details.objects.all().values(
        "id",
        "customerid",
        "fullname",
        "primarycontact",
        "soldtopartyaddress",
        "soldtopartycity",
        "soldtopartystate",
        "soldtopartypostal",
    ))

    # MUST return a list
    return JsonResponse(customers, safe=False)

def customer_address(request, customerid):
    try:
        customer = customer_details.objects.filter(customerid=customerid).values().first()

        if not customer:
            return JsonResponse({"error": "Customer not found"}, status=404)

        return JsonResponse({
            "fullname": customer.get("fullname"),
            "address": customer.get("soldtopartyaddress"),
            "city": customer.get("soldtopartycity"),
            "state": customer.get("soldtopartystate"),
            "postal": customer.get("soldtopartypostal"),
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def purchase_history(request, customerid):
    try:
        history = list(
            PurchaseHistory.objects.filter(customerid=customerid).values()
        )
        return JsonResponse({"history": history}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    


# ----------------------------
# 4. Recommendation API
# ----------------------------

# Load models on server start
BASE = os.path.dirname(os.path.abspath(__file__))

try:
    cf_model_path = os.path.join(BASE, "..", "recommender", "trained_models", "recommender_model.pkl")
    hybrid_model_path = os.path.join(BASE, "..", "recommender", "trained_models", "hybrid_recommender.pkl")

    CF_MODEL = joblib.load(cf_model_path)
    HYBRID_MODEL = joblib.load(hybrid_model_path)

    print("✅ Recommendation Models Loaded")

except Exception as e:
    print("❌ ERROR loading models:", e)
    CF_MODEL = None
    HYBRID_MODEL = None

import joblib
def generate_recommendations(customerid):
    """Runs CF + Hybrid models and returns unique results"""

    results = {}

    # ---- CF Model ----
    if CF_MODEL:
        try:
            results["cf"] = CF_MODEL.get(customerid, [])[:10]
        except:
            results["cf"] = []
    else:
        results["cf"] = []

    # ---- Hybrid Model ----
    if HYBRID_MODEL:
        try:
            results["hybrid"] = HYBRID_MODEL.get(customerid, [])[:10]
        except:
            results["hybrid"] = []
    else:
        results["hybrid"] = []

    # ---- Combine & Make Unique ----
    combined = list(dict.fromkeys(results["cf"] + results["hybrid"]))

    return {
        "cf_recommendations": results["cf"],
        "hybrid_recommendations": results["hybrid"],
        "final_recommendations": combined
    }


def get_recommendations(request, customerid):
    try:
        results = generate_recommendations(customerid)
        return JsonResponse(results, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)    



from django.db.models import Max
from crmapp.models import customer_details, PurchaseHistory

@login_required
@require_GET  
def api_get_customers(request):

    customers = list(customer_details.objects.all().values(
        "id",                      # real PK
        "customerid",              # string code
        "fullname",
        "primarycontact",
        "soldtopartyaddress",
        "soldtopartycity",
        "soldtopartystate",
        "soldtopartypostal",
    ))

    # Get last purchase using customer_ref (REAL PK)
    last_purchases = PurchaseHistory.objects.values("customer_ref").annotate(
        last_purchase=Max("purchased_at")
    )

    last_purchase_map = {
        entry["customer_ref"]: entry["last_purchase"]
        for entry in last_purchases
    }

    formatted = []
    for c in customers:
        full_address = (
            f"{c['soldtopartyaddress']}, "
            f"{c['soldtopartycity']}, "
            f"{c['soldtopartystate']} - {c['soldtopartypostal']}"
        )

        formatted.append({
            "id": c["id"],               # REAL PK
            "customerid": c["customerid"],
            "fullname": c["fullname"],
            "phone": c["primarycontact"],
            "address": full_address,
            "last_purchase": last_purchase_map.get(c["id"]),
        })

    return JsonResponse({"customers": formatted})


# ============================================================
# 1️⃣3️⃣ GET ONLY CUSTOMER PHONE (Optional)
# ============================================================
def customer_phone(request, cid):
    customer = customer_details.objects.filter(customerid=cid).first()
    if customer:
        return JsonResponse({"phone": customer.primarycontact})
    return JsonResponse({"phone": None})


def get_single_customer(request, id):
    try:
        c = customer_details.objects.get(customerid=id)
        return JsonResponse({
            "id": c.customerid,
            "fullname": c.fullname,
            "city": c.city or "",
            "state": c.state or "",
            "country": c.country or "",
            "pincode": c.pincode or "",
            "phone": str(c.primarycontact or c.secondarycontact or "")
        })
    except customer_details.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)


# ============================================================
# 1️⃣4️⃣ MESSAGE LOG VIEW
# ============================================================
def message_log_view(request):
    logs = SentMessageLog.objects.all().order_by('-created_at')[:100]
    return render(request, 'recommender/message_logs.html', {'logs': logs})

# ============================================================
# SEND MESSAGE API (Final RapBooster Version)
# ============================================================ 
import json, os, requests



# -----------------------------------------
# 🔧 Simple placeholder replace
# -----------------------------------------
def replace_placeholders(message, values: dict):
    if not message:
        return message
    for key, val in values.items():
        message = message.replace("{{" + key + "}}", str(val))
    return message


# -----------------------------------------
# 📩 Final Unified API
# ----------------------------------------- 

@login_required
@require_POST
@csrf_exempt 

# ====================================================================
#   UNIFIED API — SEND WhatsApp / Email (Templates or Custom Message)
# ====================================================================

@login_required
@csrf_exempt
@csrf_exempt
def send_message_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except:
        return HttpResponseBadRequest("Invalid JSON")

    customer_id = payload.get("customer_id")
    template_id = payload.get("template_id")
    message_body = payload.get("message_body")
    send_channel = payload.get("send_channel", "whatsapp")
    purpose = payload.get("purpose", "general")
    contract = payload.get("contract", "")
    extra = payload.get("extra", {})

    if not customer_id:
        return HttpResponseBadRequest("Missing customer_id")

    # ---------------------------------------------------------
    # Load Customer
    # ---------------------------------------------------------
    try:
        cust = customer_details.objects.get(id=customer_id)
    except customer_details.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)

    phone = str(cust.primarycontact or "").strip()
    email = cust.primaryemail or ""

    # ---------------------------------------------------------
    # Load template / message
    # ---------------------------------------------------------
    if template_id:
        try:
            template = MessageTemplates.objects.get(id=template_id)
            raw_body = template.body
        except MessageTemplates.DoesNotExist:
            return JsonResponse({"error": "Template not found"}, status=404)
    else:
        if not message_body:
            return HttpResponseBadRequest("Either template_id or message_body required")
        raw_body = message_body

    # ---------------------------------------------------------
    # Prepare Placeholder Variables
    # ---------------------------------------------------------
    variables = {
        "customer_name": cust.fullname,
        "phone": phone,
        "email": email,
        "contract": contract,
    }

    final_body = replace_placeholders(raw_body, {**variables, **extra})

    # ---------------------------------------------------------
    # SEND WHATSAPP
    # ---------------------------------------------------------
    if send_channel.lower() == "whatsapp":

        if not phone or not re.fullmatch(r"\+?\d{10,15}", phone):
            return JsonResponse({"error": "Invalid or missing phone number"}, status=400)

        status, provider = send_whatsapp_message(phone, final_body, cust)

        SentMessageLog.objects.create(
            customer=cust,
            template_id=template_id,
            recipient=phone,
            channel="whatsapp",
            rendered_body=final_body,
            status=status,
            provider_response=str(provider),
            purpose=purpose,
            contract=contract,
        )

        if status != "sent":
            return JsonResponse({
                "sent": False,
                "error": "WhatsApp sending failed",
                "provider": provider,
            }, status=400)

        return JsonResponse({
            "sent": True,
            "channel": "whatsapp",
            "message": final_body,
            "provider": provider,
            "purpose": purpose,
            "contract": contract
        })

    # ---------------------------------------------------------
    # SEND EMAIL
    # ---------------------------------------------------------
    elif send_channel.lower() == "email":

        if not email:
            return JsonResponse({"error": "Customer has no email"}, status=400)

        status, provider = send_email_message(email, "Notification", final_body)

        SentMessageLog.objects.create(
            customer=cust,
            template_id=template_id,
            recipient=email,
            channel="email",
            rendered_body=final_body,
            status=status,
            provider_response=str(provider),
            purpose=purpose,
            contract=contract
        )

        return JsonResponse({
            "sent": True,
            "channel": "email",
            "message": final_body,
            "provider": provider
        })

    # ---------------------------------------------------------
    # INVALID CHANNEL
    # ---------------------------------------------------------
    return JsonResponse({"error": "Invalid send_channel"}, status=400)



# ====================================================================
# SIMPLE API — WhatsApp Button (Customer Modal)
# ====================================================================

@csrf_exempt
def send_whatsapp(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    phone = request.POST.get("phone", "")
    message = request.POST.get("message", "")
    customer_id = request.POST.get("customer_id")

    customer = customer_details.objects.filter(id=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    status, provider = send_whatsapp_message(phone, message, customer)

    return JsonResponse({"status": status, "provider_response": provider})



# ====================================================================
# SIMPLE API — Email Button (Customer Modal)
# ====================================================================

@csrf_exempt
def send_email(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    email = request.POST.get("email", "")
    message = request.POST.get("message", "")
    subject = request.POST.get("subject", "Product Recommendation")
    customer_id = request.POST.get("customer_id")

    customer = customer_details.objects.filter(id=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    status, provider = send_email_message(email, subject, message)

    return JsonResponse({"status": status, "provider_response": provider})

from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
@login_required

def message_logs(request):
    query = request.GET.get("q", "")
    channel = request.GET.get("channel", "")
    start_date = request.GET.get("start", "")
    end_date = request.GET.get("end", "")

    logs = SentMessageLog.objects.select_related("customer")

    # 🔍 Search (full text)
    if query:
        logs = logs.filter(
            Q(message__icontains=query) |
            Q(target__icontains=query) |
            Q(provider_response__icontains=query) |
            Q(customer__name__icontains=query)
        )

    # 🔔 Filter by channel
    if channel:
        logs = logs.filter(channel=channel)

    # 📅 Date filters
    if start_date:
        logs = logs.filter(timestamp__date__gte=start_date)

    if end_date:
        logs = logs.filter(timestamp__date__lte=end_date)

    logs = logs.order_by("-timestamp")

    # 📄 Pagination (20 per page)
    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "message_logs.html", {
        "page_obj": page_obj,
        "query": query,
        "channel": channel,
        "start_date": start_date,
        "end_date": end_date,
    })

def filter_logs(request):
    query = request.GET.get("q", "")
    channel = request.GET.get("channel", "")
    start_date = request.GET.get("start", "")
    end_date = request.GET.get("end", "")

    logs = SentMessageLog.objects.select_related("customer")

    if query:
        logs = logs.filter(
            Q(message__icontains=query) |
            Q(target__icontains=query) |
            Q(provider_response__icontains=query) |
            Q(customer__name__icontains=query)
        )

    if channel:
        logs = logs.filter(channel=channel)

    if start_date:
        logs = logs.filter(timestamp__date__gte=start_date)

    if end_date:
        logs = logs.filter(timestamp__date__lte=end_date)

    return logs.order_by("-timestamp")

def export_logs_csv(request):
    logs = filter_logs(request)

    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="message_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(["Customer", "Channel", "Target", "Message", "API Response", "Timestamp"])

    for log in logs:
        writer.writerow([
            log.customer.name,
            log.channel,
            log.target,
            log.message,
            log.provider_response,
            log.timestamp,
        ])

    return response
def export_logs_excel(request):
    logs = filter_logs(request)

    wb = Workbook()
    ws = wb.active
    ws.title = "Message Logs"

    ws.append(["Customer", "Channel", "Target", "Message", "API Response", "Timestamp"])

    for log in logs:
        ws.append([
            log.customer.name,
            log.channel,
            log.target,
            log.message,
            log.provider_response,
            str(log.timestamp),
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename="message_logs.xlsx"'
    wb.save(response)

    return response

def export_logs_pdf(request):
    logs = filter_logs(request)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="message_logs.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()

    data = [
        ["Customer", "Channel", "Target", "Message", "API Response", "Timestamp"]
    ]

    for log in logs:
        data.append([
            log.customer.name,
            log.channel,
            log.target,
            log.message[:50],
            log.provider_response[:50],
            str(log.timestamp)
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))

    doc.build([table])
    return response





from crmapp.models import customer_details

def api_customers(request):
    customers = customer_details.objects.all()

    data = []
    for c in customers:
        primary = c.primarycontact if c.primarycontact else ""
        secondary = c.secondarycontact if c.secondarycontact else ""

        # Final fallback phone
        final_phone = ""
        if primary:
            final_phone = str(primary)
        elif secondary:
            final_phone = str(secondary)

        data.append({
            "customer_id": c.id,
            "customer_name": c.fullname,

            # Send all phone fields
            "primarycontact": str(primary),
            "secondarycontact": str(secondary),
            "phone": final_phone,     # REQUIRED
        })

    return JsonResponse({"customers": data})


@csrf_exempt
def rapbooster_webhook(request):
    # Allow browser GET testing
    if request.method == "GET":
        return JsonResponse({"message": "RapBooster Webhook Active", "method": "GET"})

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        data = json.loads(request.body.decode())

        message_id = data.get("message_id")
        status = data.get("status")

        if not message_id:
            return JsonResponse({"error": "message_id missing"}, status=400)

        log = SentMessageLog.objects.filter(message_id=message_id).first()

        if not log:
            return JsonResponse({"error": "No log found for message_id"}, status=404)

        status_mapping = {
            "sent": "sent",
            "delivered": "delivered",
            "read": "read",
            "failed": "failed",
            "queued": "queued"
        }

        log.status = status_mapping.get(status, "sent")
        log.provider_response = json.dumps(data)
        log.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

from crmapp.models import SentMessageLog, customer_details

def message_timeline_api(request, customer_id):
    logs = SentMessageLog.objects.filter(customer_id=customer_id).order_by("-created_at")

    data = []
    for log in logs:
        data.append({
            "id": log.id,
            "recipient": log.recipient,
            "channel": log.channel,
            "rendered_subject": log.rendered_subject,
            "rendered_body": log.rendered_body,
            "status": log.status,
            "message_id": log.message_id,
            "provider_response": log.provider_response,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": log.updated_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({"timeline": data})

# ---------------- PURCHASE HISTORY API ----------------

@require_GET 

# ----------- PURCHASE HISTORY API ----------- 

def get_purchase_history(request, customer_code):

    # Correct filtering using business customer code
    history = PurchaseHistory.objects.filter(
        customer__customerid=customer_code
    ).order_by("-purchased_at")

    data = []

    for row in history:
        # Product name logic
        product_name = (
            row.product.product_name if row.product else row.product_name
        )

        data.append({
            "product_name": product_name,
            "quantity": float(row.quantity),
            "total_amount": float(row.total_amount),
            "invoice_type": row.invoice_type,
            "purchased_at": row.purchased_at.strftime("%Y-%m-%d"),
        })

    return JsonResponse({"purchase_history": data})

# -------------------------------------------------------
# INTERNAL: Build unified purchase history list
# -------------------------------------------------------
def build_purchase_history(real_id, business_id):
    results = []

    # =====================================================
    # 1. NEW PurchaseHistory table (most reliable)
    # =====================================================
    ph_items = PurchaseHistory.objects.filter(customer_ref=real_id)
    for ph in ph_items:
        results.append({
            "product_id": getattr(ph.product, "product_id", None),
            "product_name": (
                ph.product.product_name if getattr(ph, "product", None)
                else ph.product_name
            ),
            "quantity": float(ph.quantity or 0),
            "total_amount": float(ph.total_amount or 0),
            "date": ph.purchased_at,
            "source": "purchase_history"
        })

    # =====================================================
    # 2. ServiceProduct → Product (FK)
    # =====================================================
    sp_items = ServiceProduct.objects.filter(service__custid_id=business_id)

    for s in sp_items:
        results.append({
            "product_id": s.product_id,
            "product_name": s.product.product_name,
            "quantity": None,
            "total_amount": None,
            "date": getattr(s.service, "date", None),
            "source": "service_product"
        })

    # =====================================================
    # 3. invoice → fuzzy match Product
    # =====================================================
    inv_items = invoice.objects.filter(custid_id=business_id)

    for inv in inv_items:
        rawname = (inv.description_of_goods or "").strip()
        if not rawname:
            continue

        # attempt to match product
        match = Product.objects.filter(
            Q(product_name__icontains=rawname)
        ).first()

        if match:
            results.append({
                "product_id": match.product_id,
                "product_name": match.product_name,
                "quantity": inv.quantity if hasattr(inv, "quantity") else None,
                "total_amount": inv.taxable_value if hasattr(inv, "taxable_value") else None,
                "date": inv.invoice_date,
                "source": "invoice"
            })

    # =====================================================
    # Sort final combined history by DATE descending
    # =====================================================
    results_sorted = sorted(
        results,
        key=lambda x: x["date"] or "",
        reverse=True
    )

    return results_sorted


# -------------------------------------------------------
# PUBLIC API: /api/purchase-history/<cid>/
# -------------------------------------------------------
@require_GET 

# -------------------------------------------------------------
# 2. Purchase History (Fix: customer_code instead of id) 


def api_purchase_history(request, customer_code):

    try:
        # Fetch customer using provided customer_code (customerid)
        customer = customer_details.objects.get(customerid=customer_code)

        # Fetch all purchase history linked via customer_int
        history = list(
            PurchaseHistory.objects.filter(
                customer_int=customer.id
            ).values(
                "id",
                "product_name",
                "quantity",
                "total_amount",
                "invoice_type",
                "purchased_at",
                "invoice_id",
                "tax_invoice_id",
                "product_id"
            ).order_by("-purchased_at")
        )

        return JsonResponse({
            "customer": {
                "id": customer.id,
                "customer_code": customer.customerid,
                "fullname": customer.fullname,
                "mobile": customer.primarycontact
            },
            "purchase_history": history
        })

    except customer_details.DoesNotExist:
        return JsonResponse({
            "error": "Customer not found",
            "purchase_history": []
        }, status=404)


# -------------------------------------------------------------
# 3. Demographic Recommendation
# -------------------------------------------------------------
def api_demographic_recommendation(request, customer_code):

    try:
        cust = customer_details.objects.get(customerid=customer_code)
    except customer_details.DoesNotExist:
        return JsonResponse({"recommendations": [], "error": "Customer not found"})

    # Filter similar customers
    similar_customers = customer_details.objects.filter(
        soldtopartycity=cust.soldtopartycity,
        soldtopartystate=cust.soldtopartystate,
        soldtopartypostal=cust.soldtopartypostal
    ).exclude(id=cust.id)

    # Aggregate popular items
    product_counts = (
        PurchaseHistory.objects.filter(customer_ref__in=similar_customers.values("id"))
        .values("product_name")
        .order_by()
    )

    product_list = [p["product_name"] for p in product_counts]

    return JsonResponse({
        "customer": cust.fullname,
        "city": cust.soldtopartycity,
        "state": cust.soldtopartystate,
        "region": cust.soldtopartypostal,
        "recommendations": product_list[:10]
    })




def api_personalized_recommendation(request, customer_code):
    """
    Returns AI personalized recommendations for a customer.
    Frontend uses BUSINESS customerid (string), 
    but recommendation model requires REAL PK (int).
    """

    # ----------------------------------------------------------------------
    # 1. Validate customer exists using business code
    # ----------------------------------------------------------------------
    try:
        cust = customer_details.objects.get(customerid=customer_code)
    except customer_details.DoesNotExist:
        return JsonResponse(
            {"error": "Customer not found", "recommendations": []},
            status=404
        )

    real_customer_id = cust.id  # PK needed for ML model

    # ----------------------------------------------------------------------
    # 2. Generate recommendations using hybrid model
    # ----------------------------------------------------------------------
    if hybrid_model is None:
        return JsonResponse({
            "error": "Hybrid model not loaded",
            "recommendations": []
        })

    try:
        raw_recommendations = hybrid_model.predict([real_customer_id])
    except Exception as e:
        return JsonResponse({
            "error": f"Model prediction failed: {e}",
            "recommendations": []
        })

    # ----------------------------------------------------------------------
    # 3. Normalize results (if model returns objects or strings)
    # ----------------------------------------------------------------------
    final_recs = []

    for item in raw_recommendations:
        try:
            # allow dict, object, or raw string
            if isinstance(item, dict):
                final_recs.append({
                    "product_id": item.get("product_id"),
                    "title": item.get("title") or item.get("product_name"),
                    "category": item.get("category"),
                    "tags": item.get("tags"),
                    "confidence_score": item.get("score"),
                })

            else:  
                # fallback: treat as raw product name
                final_recs.append({
                    "product_id": None,
                    "title": str(item),
                    "category": None,
                    "tags": None,
                    "confidence_score": None
                })

        except Exception:
            continue

    # ----------------------------------------------------------------------
    # 4. JSON Response
    # ----------------------------------------------------------------------
    return JsonResponse({
        "customer_id": real_customer_id,
        "customer_code": customer_code,
        "customer_name": cust.fullname,
        "recommendations": final_recs
    })



from django.http import JsonResponse
from django.db import connection
import pickle
import os

# ---------------------------------------------------------
# Load Model Once
# ---------------------------------------------------------
MODEL_FILE = os.path.join("recommender", "trained_models", "simple_cf_model.pkl")

try:
    with open(MODEL_FILE, "rb") as f:
        model = pickle.load(f)
except Exception as e:
    model = None
    print("ERROR LOADING MODEL:", e)


# ---------------------------------------------------------
# Helper: Fetch user purchase history
# ---------------------------------------------------------
def get_user_history(customer_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT product_name 
            FROM crmapp_purchasehistory
            WHERE customer_id = %s
        """, [customer_id])
        rows = cursor.fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------
# Main Recommendation API
# ---------------------------------------------------------
def get_recommendations(request, customer_id):

    # Validate customer_id
    try:
        customer_id = int(customer_id)
    except ValueError:
        return JsonResponse({"error": "Invalid customer_id"}, status=400)

    # Check if model loaded
    if model is None:
        return JsonResponse({"error": "Model not loaded"}, status=500)

    # Fetch history
    history = get_user_history(customer_id)

    # If user has no history
    if not history:
        return JsonResponse({
            "customer_id": customer_id,
            "recommended_products": [],
            "message": "No purchase history found for this customer."
        })

    # Generate recommendations
    try:
        recommendations = model.recommend(customer_id)
    except Exception as e:
        return JsonResponse({"error": f"Model error: {e}"}, status=500)

    return JsonResponse({
        "customer_id": customer_id,
        "recommended_products": recommendations
    })

MODEL_PATH = "recommender/trained_models/simple_cf_model.pkl"

# ----------------------------------------------------
# Load model once (when server starts)
# ----------------------------------------------------
if os.path.exists(MODEL_PATH):
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    pivot = model["pivot"]
    similarity = model["similarity"]
else:
    model = None
    pivot = None
    similarity = None

 

# --------------------------------------------------
# Load ML model once (on server start)
# --------------------------------------------------
MODEL_FILE = "recommender/trained_models/simple_cf_model.pkl"

try:
    with open(MODEL_FILE, "rb") as f:
        model = pickle.load(f)
    pivot = model["pivot"]
    similarity = model["similarity"]

    MODEL_READY = True
    print("🔵 ML Model loaded in Django successfully.")

except Exception as e:
    MODEL_READY = False
    pivot = None
    similarity = None
    print("🔴 Failed to load ML model:", str(e))


# --------------------------------------------------
# Recommendation Function
# --------------------------------------------------
def generate_recommendations(customer_id, top_n=5):

    if pivot is None:
        return {
            "status": "ERROR",
            "message": "ML model not loaded"
        }

    if customer_id not in pivot.index:
        return {
            "status": "NO_DATA",
            "customer_id": customer_id,
            "products": []
        }

    # Find customer index
    cust_idx = pivot.index.tolist().index(customer_id)

    # Similarity row
    sim_scores = list(enumerate(similarity[cust_idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Top similar users excluding self
    similar_users = [u for u, _ in sim_scores[1:6]]

    # Aggregate their purchases
    similar_products = pivot.iloc[similar_users].sum(axis=0)

    # Remove purchased items
    own = pivot.loc[customer_id]
    filtered = similar_products[own == 0]

    # Sort
    final = filtered.sort_values(ascending=False).head(top_n)

    return {
        "status": "OK",
        "customer_id": customer_id,
        "recommended_products": list(final.index),
        "scores": list(final.values)
    }


# --------------------------------------------------
# Django API Endpoint for Recommendation System
# --------------------------------------------------

from .ml_service import get_recommendations



@csrf_exempt 

@csrf_exempt
def get_recommendations(request, customer_id):
    # ---------------------------
    # DO NOT CONVERT TO INT
    # customer_id is STRING
    # Example: "SANKAP4923"
    # ---------------------------

    if model is None:
        return JsonResponse({"error": "Model not loaded"}, status=500)

    # Validate customer_id string
    if not isinstance(customer_id, str):
        return JsonResponse({"error": "Invalid customer_id"}, status=400)

    # ---------------------------
    # Fetch purchase history
    # ---------------------------
    from crmapp.models import PurchaseHistory

    history = list(
        PurchaseHistory.objects.filter(customer_id=customer_id)
        .values("product_name", "product_id", "quantity", "total_amount", "purchased_at")
        .order_by("-purchased_at")
    )

    if not history:
        return JsonResponse({
            "customer_id": customer_id,
            "recommended_products": [],
            "message": "No purchase history found for this customer."
        })

    # ---------------------------
    # Generate Recommendations
    # ---------------------------
    try:
        recommendations = model.recommend(customer_id)
    except Exception as e:
        return JsonResponse({"error": f"Model error: {str(e)}"}, status=500)

    # ---------------------------
    # Final Response
    # ---------------------------
    return JsonResponse({
        "customer_id": customer_id,
        "purchase_history": history,
        "recommended_products": recommendations
    })


    # -------------------------
    # Generate Recommendations
    # -------------------------
    try:
        recommendations = generate_recommendations(customer_id)
    except Exception as e:
        return JsonResponse(
            {"status": False, "error": f"Internal error: {str(e)}"},
            status=500
        )

    # Final successful response
    return JsonResponse(
        {
            "status": True,
            "customer_id": customer_id,
            "recommendations": recommendations
        },
        status=200
    )
# --------------------------------------------
# Load trained CF model once at server startup
# -------------------------------------------- 
@login_required
@csrf_exempt
def get_recommendation_api(request, customer_id):
    """
    API: /api/get-recommendations/<customer_id>/
    """

    try:
        customer_id = int(customer_id)
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid customer_id format.",
            "recommendations": []
        }, status=400)

    result = get_recommendations(customer_id=customer_id, top_n=5)
    return JsonResponse(result, status=200, safe=False)

from django.http import JsonResponse
from .hybrid_service import get_hybrid_recommendations

def api_get_recommendations(request):
    customer_id = request.GET.get("customer_id")

    if not customer_id:
        return JsonResponse({"error": "customer_id is required"}, status=400)

    recs = get_hybrid_recommendations(customer_id)

    if isinstance(recs, dict) and "error" in recs:
        return JsonResponse({"error": recs["error"]}, status=500)

    return JsonResponse({
        "customer_id": customer_id,
        "engine": "hybrid",
        "recommendations": recs
    })

# ============================================================
# 1) GET ML RECOMMENDATIONS
# ============================================================
@login_required
def api_get_ml_recommendations(request):
    try:
        customer_id = request.GET.get("customer_id")

        if not customer_id:
            return JsonResponse({"status": "error", "message": "Customer ID missing"}, status=400)

        recommendations = get_recommendations_for_customer(customer_id)

        return JsonResponse({
            "status": "success",
            "customer_id": customer_id,
            "recommendations": recommendations
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }, status=500)
 
# 2) GET CONTENT-BASED RECOMMENDATIONS (BY HISTORY)
# ============================================================
@login_required
def api_get_purchase_history(request):
    """
    Returns content-based product list from PurchaseHistory.
    """
    try:
        customer_id = request.GET.get("customer_id")

        if not customer_id:
            return JsonResponse({"status": "error", "message": "Customer ID missing"}, status=400)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT product_name, quantity, purchase_date
                FROM crmapp_purchasehistory
                WHERE customer_id = %s
                ORDER BY purchase_date DESC
                LIMIT 10
            """, [customer_id])

            rows = cursor.fetchall()

        history = [
            {
                "product_name": r[0],
                "quantity": float(r[1]) if r[1] else None,
                "purchase_date": str(r[2])
            } for r in rows
        ]

        return JsonResponse({
            "status": "success",
            "data": history
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
        

@require_GET
def fetch_saved_recommendations(request):
    customer_id = request.GET.get("customer_id")

    if not customer_id:
        return HttpResponseBadRequest("customer_id is required")

    recs = PestRecommendation.objects.filter(customer_id=customer_id).order_by("-created_at")

    return JsonResponse({
        "customer_id": customer_id,
        "count": recs.count(),
        "data": list(recs.values())
    })


#1
# recommender/views.py

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import connection

from .hybrid_service import get_hybrid_recommendations
from .recommender_engine import get_cf_recommendations
from .recommender_engine import get_content_based_recommendations


# ---------------------------------------------------------
# UTIL: Fetch Customer Info
# ---------------------------------------------------------
def fetch_customer_details(customer_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, fullname, primaryemail, primarycontact,
                   soldtopartyaddress, soldtopartycity, soldtopartystate,
                   soldtopartypostal
            FROM crmapp_customer_details
            WHERE customerid = %s
        """, [customer_id])
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "internal_id": row[0],
        "fullname": row[1],
        "email": row[2],
        "contact": row[3],
        "address": row[4],
        "city": row[5],
        "state": row[6],
        "postal": row[7],
    }


# ---------------------------------------------------------
# UTIL: Fetch Purchase History
# ---------------------------------------------------------
def fetch_purchase_history(customer_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT product_name, quantity, total_amount, purchased_at
            FROM crmapp_purchasehistory
            WHERE customer_id = %s
            ORDER BY purchased_at DESC
            LIMIT 50
        """, [customer_id])

        rows = cursor.fetchall()

    return [
        {
            "product_name": r[0],
            "quantity": float(r[1]),
            "total_amount": float(r[2]),
            "purchased_at": r[3].strftime("%Y-%m-%d %H:%M")
        }
        for r in rows
    ]


# ---------------------------------------------------------
# UPSALE / CROSS-SALE
# ---------------------------------------------------------
def generate_upsell_and_crosssell(base_product_id):
    """
    Upsell = higher-priced version of same category
    Cross-sell = frequently bought together
    """

    with connection.cursor() as cursor:

        # Upsell: same category, higher price
        cursor.execute("""
            SELECT id, product_name, selling_price
            FROM crmapp_productdetails
            WHERE category = (
                SELECT category FROM crmapp_productdetails WHERE id = %s
            )
            AND selling_price > (
                SELECT selling_price FROM crmapp_productdetails WHERE id = %s
            )
            ORDER BY selling_price ASC
            LIMIT 5
        """, [base_product_id, base_product_id])

        upsell_rows = cursor.fetchall()

        # Cross-sell
        cursor.execute("""
            SELECT p.id, p.product_name, p.selling_price
            FROM crmapp_productdetails p
            JOIN crmapp_purchasehistory ph
                ON p.id = ph.product_id
            WHERE ph.product_id != %s
            ORDER BY p.selling_price DESC
            LIMIT 5
        """, [base_product_id])

        crosssell_rows = cursor.fetchall()

    return {
        "upsell": [
            {"product_id": r[0], "name": r[1], "price": float(r[2])}
            for r in upsell_rows
        ],
        "crosssell": [
            {"product_id": r[0], "name": r[1], "price": float(r[2])}
            for r in crosssell_rows
        ]
    }


# ---------------------------------------------------------
# MAIN API: UNIFIED RECOMMENDATION ENGINE
# ---------------------------------------------------------
@require_GET
def unified_recommendation_api(request):
    customer_id = request.GET.get("customer_id")

    if not customer_id:
        return HttpResponseBadRequest("customer_id required")

    # Fetch supporting data
    customer = fetch_customer_details(customer_id)
    purchase_history = fetch_purchase_history(customer_id)

    # Run 3 engines
    hybrid = get_hybrid_recommendations(customer_id, top_n=10)
    cf = get_cf_recommendations(customer_id, top_n=10)
    content = get_content_based_recommendations(customer_id, top_n=10)

    return JsonResponse({
        "customer": customer,
        "purchase_history": purchase_history,
        "recommendations": {
            "hybrid": hybrid,
            "collaborative_filtering": cf,
            "content_based": content
        }
    }, safe=False)


# ---------------------------------------------------------
# API: CF only
# ---------------------------------------------------------
@require_GET
def cf_api(request):
    customer_id = request.GET.get("customer_id")
    if not customer_id:
        return HttpResponseBadRequest("customer_id required")

    return JsonResponse(get_cf_recommendations(customer_id), safe=False)


# ---------------------------------------------------------
# API: Content-based only
# ---------------------------------------------------------
@require_GET
def content_api(request):
    customer_id = request.GET.get("customer_id")
    if not customer_id:
        return HttpResponseBadRequest("customer_id required")

    return JsonResponse(get_content_based_recommendations(customer_id), safe=False)


# ---------------------------------------------------------
# API: Hybrid only
# ---------------------------------------------------------
@require_GET
def hybrid_api(request):
    customer_id = request.GET.get("customer_id")
    if not customer_id:
        return HttpResponseBadRequest("customer_id required")

    return JsonResponse(get_hybrid_recommendations(customer_id), safe=False)


# ---------------------------------------------------------
# API: Upsell + Cross-sell (button click)
# ---------------------------------------------------------
@require_GET
def upsell_crosssell_api(request):
    product_id = request.GET.get("product_id")

    if not product_id:
        return HttpResponseBadRequest("product_id required")

    return JsonResponse(generate_upsell_and_crosssell(product_id), safe=False)



@csrf_exempt
def purchase_history(request, customer_id):
    try:
        with connection.cursor() as cursor:

            # Convert path parameter to int (customer_int)
            try:
                cid_int = int(customer_id)
            except:
                cid_int = None

            query = """
                SELECT 
                    id,
                    product_name,
                    quantity,
                    total_amount,
                    invoice_type,
                    purchased_at,
                    customer_id,
                    customer_int,
                    invoice_id
                FROM crmapp_purchasehistory
                WHERE customer_int = %s
                ORDER BY purchased_at DESC
                LIMIT 100;
            """

            cursor.execute(query, [cid_int])
            rows = cursor.fetchall()

        # No history found
        if not rows:
            return JsonResponse({
                "status": True,
                "customer_id": customer_id,
                "history": []
            })

        # Format result
        history = []
        for row in rows:
            history.append({
                "id": row[0],
                "product_name": row[1],
                "quantity": float(row[2]),
                "total_amount": float(row[3]),
                "invoice_type": row[4],
                "purchased_at": row[5].strftime("%Y-%m-%d %H:%M"),
                "customer_code": row[6],     # SANKAP4923, etc.
                "customer_int": row[7],
                "invoice_id": row[8]
            })

        return JsonResponse({
            "status": True,
            "customer_id": customer_id,
            "history": history
        })

    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)}, status=500)


from django.views.decorators.http import require_GET 
from django.views.decorators.http import require_GET
from django.http import JsonResponse

from crmapp.models import Product, customer_details
 

from rest_framework.decorators import api_view
from rest_framework.response import Response
from crmapp.models import PurchaseHistory, customer_details
from .serializers import PurchaseHistorySerializer
from .purchase_history_serializer import PurchaseHistorySerializer

@api_view(["GET"])
def get_purchase_history(request, customer_code):
    try:
        customer = customer_details.objects.get(customerid=customer_code)
    except customer_details.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    history = PurchaseHistory.objects.filter(customer=customer).order_by("-purchased_at")

    serializer = PurchaseHistorySerializer(history, many=True)

    return Response({
        "customer": customer.fullname,
        "customer_id": customer.customerid,
        "purchase_history_count": len(serializer.data),
        "purchase_history": serializer.data
    })


from datetime import datetime

 
from datetime import date, timedelta

from datetime import date
from django.http import JsonResponse
from crmapp.models import CustomerContract, customer_details,service_management


# -------------------------------------------------------
# 📌 FETCH CONTRACT (WORKS WITH STRING customer_id) 

def get_customer_contract(request, customer_id):

    try:
        # customer_id from frontend is customer.customerid (string)
        customer = customer_details.objects.get(customerid=customer_id)

        # latest service record (contract)
        service = service_management.objects.filter(
            customer_id=customer.id
        ).latest("service_date")

        return JsonResponse({
            "exists": True,
            "contract_type": service.contract_type,
            "start_date": service.service_date,
            "lead_date": service.lead_date,
            "status": service.contract_status,
            "service_id": service.id,
        })

    except service_management.DoesNotExist:
        return JsonResponse({"exists": False})

    except customer_details.DoesNotExist:
        return JsonResponse({"exists": False})


@csrf_exempt
def save_customer_contract(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"})

    try:
        data = json.loads(request.body)

        # Frontend sends customerid (string code) → find real PK
        customer_code = data.get("customer_id")
        contract_type = data.get("contract_type")
        start_date = data.get("start_date")

        if not (customer_code and contract_type and start_date):
            return JsonResponse({"success": False, "error": "Missing fields"})

        # Get REAL customer object
        customer = customer_details.objects.get(customerid=customer_code)

        # -------------------------
        # 1️⃣ Save in service management (REAL CONTRACT TABLE)
        # -------------------------
        service = service_management.objects.create(
            customer_id=customer.id,
            contract_type=contract_type,
            contract_status="Active",
            state=customer.soldtopartystate,
            city=customer.soldtopartycity,
            pincode=customer.soldtopartypostal,
            address=customer.soldtopartyaddress,
            payment_terms="Standard",
            frequency_count="1",
            lead_date=date.today(),
            service_date=start_date,
            gst_status="Yes",
            service_subject=f"{contract_type} Contract"
        )

        # -------------------------
        # 2️⃣ SAVE DEFAULT LINE-ITEM IN SERVICEPRODUCT
        # -------------------------
        # Fetch any product belonging to this contract type (optional logic)
        default_product = Product.objects.filter(
            product_name__icontains=contract_type.split()[0]
        ).first()

        if default_product:
            ServiceProduct.objects.create(
                service_id=service.id,
                product_id=default_product.product_id,
                price=0,
                quantity=1,
                gst_percentage=0,
                total_with_gst=0,
                description=f"{contract_type} Base Contract"
            )

        return JsonResponse({
            "success": True,
            "message": "Contract saved successfully",
            "service_id": service.id
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


from django.http import JsonResponse
from .demographic_service import (
    get_demographic_recommendations,
    save_demographic_recommendations
)
from .models import PestRecommendation


def generate_demographic_recommendations(request, customer_id):
    try:
        customer_pk = int(customer_id)
        customer_details.objects.get(id=customer_pk)  # validate FK
    except:
        return JsonResponse({"status": "error", "message": "Invalid customer ID"})

    result = get_demographic_recommendations(customer_pk)

    if result["status"] != "success":
        return JsonResponse(result)

    # Delete old demographic rows
    PestRecommendation.objects.filter(
        customer_id=customer_pk,
        recommendation_type="demographic"
    ).delete()

    formatted = [
        {"product_id": pid, "score": 1.0}
        for pid in result["recommended_products"]
    ]

    save_demographic_recommendations(customer_pk, formatted)

    return JsonResponse({
        "status": "success",
        "city": result["city"],
        "state": result["state"],
        "postal_code": result["postal_code"],
        "total_products": result["total_products"]
    })

from django.http import JsonResponse
from .recommender_engine import generate_full_recommendations


def generate_recommendations(request, customer_id):
    """
    Universal API — Hybrid + Demographic
    """
    result = generate_full_recommendations(customer_id, top_n=10)
    return JsonResponse(result, safe=False)


from django.http import JsonResponse
from .demographic_service import get_demographic_recommendations, save_demographic_recommendations

def demographic_recommend_api(request, customer_id):
    result = get_demographic_recommendations(customer_id)

    if result["status"] != "success":
        return JsonResponse(result, status=404)

    # Save to DB
    save_demographic_recommendations(
        customer_id,
        [{"product_id": item["product_id"], "score": item["score"]}
         for item in result["recommended_products"]]
    )

    return JsonResponse(result, safe=False)



from django.http import JsonResponse
from crmapp.models import service_management


def service_purchase_history(request, customer_id):
    services = (
        service_management.objects
        .filter(customer_id=customer_id)
        .order_by('-service_date', '-lead_date')
    )

    result = []

    for s in services:
        result.append({
            "service_name": s.service_subject or "Service",
            "contract_type": s.contract_type,
            "status": s.contract_status,
            "amount": float(s.total_price_with_gst or 0),
            "start_date": (
                s.service_date.isoformat()
                if s.service_date else
                s.lead_date.isoformat()
            )
        })

    return JsonResponse({"services": result})
