# recommender/api_views.py
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from recommender.models import Item
from crmapp.models import customer_details, TaxInvoice, TaxInvoiceItem
import json
import requests

# recommender/api_views.py
import json
import re
import logging
import requests
import os
 
from django.views.decorators.http import require_GET, require_POST
 
from django.contrib.auth.decorators import login_required

from crmapp.models import customer_details, PurchaseHistory, MessageTemplates, SentMessageLog, Product
from .rapbooster_api import send_recommendation_message, send_whatsapp_message, send_email_message


# RAP BOOSTER settings
RAPBOOSTER_API_KEY = "6538c8eff027d41e9151"
RAPBOOSTER_API_URL = "https://rapbooster.in/api/send"


logger = logging.getLogger(__name__)

# --------------------------
# Helper: simple placeholder replace
# --------------------------
def simple_replace(message: str, values: dict):
    if not message:
        return ""
    for k, v in (values or {}).items():
        message = message.replace("{{" + k + "}}", str(v))
    return message

# --------------------------
# GET /api/customers/
# Returns: { customers: [ {customer_id, customer_name, primarycontact, secondarycontact, phone} ] }
# --------------------------
@require_GET
def api_get_customers(request):
    try:
        qs = customer_details.objects.all().values(
            "id", "fullname", "primarycontact", "secondarycontact"
        )
        customers = []
        for c in qs:
            primary = c.get("primarycontact") or ""
            secondary = c.get("secondarycontact") or ""
            phone = primary or secondary or ""
            customers.append({
                "customer_id": c["id"],
                "customer_name": c["fullname"],
                "primarycontact": str(primary) if primary is not None else "",
                "secondarycontact": str(secondary) if secondary is not None else "",
                "phone": str(phone),
            })
        return JsonResponse({"customers": customers})
    except Exception as e:
        logger.exception("api_get_customers error")
        return JsonResponse({"error": str(e)}, status=500)

# --------------------------
# GET /api/customer/<id>/details/
# Returns address and purchase_history: [{product_name, quantity, timestamp}, ...]
# --------------------------
@require_GET
def api_customer_details(request, cid):
    try:
        # Accept both numeric and string ids
        customer = customer_details.objects.filter(id=cid).first()
        if not customer:
            return JsonResponse({"error": "Customer not found"}, status=404)

        # Address fields — adapt to your model field names if needed
        address_parts = []
        for f in ("soldtopartyaddress", "soldtopartycity", "soldtopartystate", "soldtopartypostal"):
            val = getattr(customer, f, None)
            if val:
                address_parts.append(str(val))
        address = ", ".join(address_parts).strip()

        # Purchase history: use PurchaseHistory model (or adjust if you use different name)
        purchases = []
        ph_qs = PurchaseHistory.objects.filter(customer=customer).order_by("-purchased_at")[:200]
        for p in ph_qs:
            # product link: if FK to Product
            prod_name = ""
            try:
                if p.product:
                    prod_name = getattr(p.product, "product_name", "") or ""
                else:
                    prod_name = p.product_name or ""
            except Exception:
                prod_name = p.product_name or ""

            ts = getattr(p, "purchased_at", None)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""

            purchases.append({
                "product_name": prod_name,
                "quantity": float(getattr(p, "quantity", 0) or 0),
                "timestamp": ts_str
            })

        return JsonResponse({
            "customer_id": customer.id,
            "customer_name": getattr(customer, "fullname", ""),
            "address": address,
            "purchase_history": purchases
        })
    except Exception as e:
        logger.exception("api_customer_details error")
        return JsonResponse({"error": str(e)}, status=500)

# --------------------------
# POST /api/send-message/
# Body example:
# {
#   "customer_id": 27,
#   "template_id": 5,            # optional
#   "message_body": "raw text",  # required if template_id missing
#   "send_channel": "whatsapp",  # optional, default whatsapp
#   "contract": "3 Months",      # optional
#   "extra": { "product": "X" }  # optional placeholders
# }
# --------------------------
@csrf_exempt
@require_POST
def api_send_message(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    customer_id = payload.get("customer_id")
    template_id = payload.get("template_id")
    message_body = payload.get("message_body")  # raw fallback
    send_channel = (payload.get("send_channel") or "whatsapp").lower()
    contract = payload.get("contract", "")
    extra = payload.get("extra", {}) or {}

    if not customer_id:
        return HttpResponseBadRequest("Missing customer_id")

    try:
        customer = customer_details.objects.get(id=customer_id)
    except customer_details.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)

    # Determine raw template/body
    raw = ""
    template_obj = None
    if template_id:
        try:
            template_obj = MessageTemplates.objects.get(id=template_id)
            raw = template_obj.body or ""
        except MessageTemplates.DoesNotExist:
            return JsonResponse({"error": "Template not found"}, status=404)
    else:
        if not message_body:
            return HttpResponseBadRequest("Either template_id or message_body required")
        raw = message_body

    # Build placeholder values
    base_vars = {
        "customer_name": getattr(customer, "fullname", "") or "",
        "phone": str(getattr(customer, "primarycontact", "") or getattr(customer, "secondarycontact", "") or ""),
        "email": getattr(customer, "email", "") or "",
        "contract": contract or ""
    }
    all_vars = {**base_vars, **(extra or {})}

    final_message = simple_replace(raw, all_vars)

    # Send based on channel
    try:
        if send_channel == "whatsapp":
            phone = base_vars["phone"]
            if not phone or not re.fullmatch(r"\+?\d{10,15}", phone):
                return JsonResponse({"error": "Invalid or missing phone number for customer"}, status=400)

            # Use your rapbooster helper if available
            # Example signature: send_recommendation_message(phone_number=..., message=..., customer_name=...)
            # Fallback: call RapBooster REST endpoint directly
            try:
                # prefer internal helper if it exists
                if hasattr(send_recommendation_message, "__call__"):
                    status_code, provider_resp = send_recommendation_message(phone_number=phone, message=final_message, customer_name=customer.fullname)
                    success = status_code == 200
                else:
                    # fallback direct call
                    RB_KEY = os.getenv("RAPBOOSTER_API_KEY") or "6538c8eff027d41e9151"
                    RB_URL = "https://api.rapbooster.com/v1/send"
                    resp = requests.post(RB_URL, json={"apikey": RB_KEY, "phone": phone, "message": final_message}, timeout=10)
                    provider_resp = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
                    success = resp.status_code == 200 and provider_resp.get("status") == "success"

            except Exception as e:
                logger.exception("RapBooster send error")
                success = False
                provider_resp = {"error": str(e)}

            # Log message
            try:
                SentMessageLog.objects.create(
                    template=template_obj if template_obj else None,
                    recipient=phone,
                    channel="whatsapp",
                    rendered_body=final_message,
                    status="success" if success else "failed",
                    provider_response=str(provider_resp)
                )
            except Exception:
                logger.exception("Failed to log SentMessage")

            if not success:
                return JsonResponse({"sent": False, "provider_response": provider_resp}, status=400)

            return JsonResponse({"sent": True, "provider_response": provider_resp})

        elif send_channel == "email":
            email = base_vars["email"]
            if not email:
                return JsonResponse({"error": "Customer has no email"}, status=400)

            # Use your send_email_message helper
            try:
                result = send_email_message(email, payload.get("subject", "Notification"), final_message)
                SentMessageLog.objects.create(
                    template=template_obj if template_obj else None,
                    recipient=email,
                    channel="email",
                    rendered_body=final_message,
                    status="success",
                    provider_response=str(result)
                )
                return JsonResponse({"sent": True, "email_response": result})
            except Exception as e:
                logger.exception("Email send error")
                return JsonResponse({"sent": False, "error": str(e)}, status=500)

        else:
            return JsonResponse({"error": "Unknown send_channel"}, status=400)

    except Exception as e:
        logger.exception("api_send_message error")
        return JsonResponse({"error": str(e)}, status=500)


# -------------------------
# Product list for UI
# -------------------------
def product_list(request):
    products = list(Item.objects.order_by("title").values_list("title", flat=True))
    return JsonResponse({"products": products})


# -------------------------
# Customers list for UI
# -------------------------
def customer_list(request):
    # returns list of { customer_id, customer_name }
    qs = customer_details.objects.all().values("id", "fullname")
    data = [{"customer_id": c["id"], "customer_name": c["fullname"]} for c in qs]
    return JsonResponse({"customers": data})


# -------------------------
# Customer detail / phone
# -------------------------
def customer_phone(request, cid):
    try:
        c = customer_details.objects.get(id=cid)
    except customer_details.DoesNotExist:
        return JsonResponse({"error": "Customer not found."}, status=404)

    # Try primarycontact then secondarycontact
    phone = None
    if hasattr(c, "primarycontact") and c.primarycontact:
        phone = str(c.primarycontact)
    elif hasattr(c, "secondarycontact") and c.secondarycontact:
        phone = str(c.secondarycontact)

    return JsonResponse({
        "customer_id": c.id,
        "customer_name": getattr(c, "fullname", ""),
        "phone": phone
    })


# -------------------------
# Content-based recommendations
# -------------------------
def get_recommendations(request):
    product_name = request.GET.get("product", "").strip()
    if not product_name:
        return JsonResponse({"error": "Please provide a product name."}, status=400)

    product = Item.objects.filter(title__icontains=product_name).first()
    if not product:
        return JsonResponse({"error": "Product not found."}, status=404)

    similar_products = Item.objects.filter(category=product.category).exclude(id=product.id)[:6]
    return JsonResponse({
        "base_product": product.title,
        "recommended_products": [p.title for p in similar_products]
    })


# -------------------------
# Personalized / Collaborative recommendations (for customer)
# Returns {"recommendations": ["Product A", "Product B", ...]}
# -------------------------
def user_recommendations(request, customer_id):
    invoices = TaxInvoice.objects.filter(customer_id=customer_id)
    if not invoices.exists():
        return JsonResponse({"recommendations": []})

    # products this customer purchased
    purchased_product_ids = TaxInvoiceItem.objects.filter(invoice__in=invoices).values_list("product_id", flat=True)

    # Find other invoice items co-purchased by other customers (excluding customer's products)
    co_purchased = (TaxInvoiceItem.objects
                    .exclude(product_id__in=purchased_product_ids)
                    .values("product_id")
                    .annotate(cnt=Count("product_id"))
                    .order_by("-cnt")[:8])

    # Map product_id -> product title using Item model (best effort)
    product_titles = []
    for entry in co_purchased:
        pid = entry["product_id"]
        item = Item.objects.filter(id=pid).first()
        if item:
            product_titles.append(item.title)
        else:
            # fallback to product_id string if no Item row
            product_titles.append(f"Product-{pid}")

    return JsonResponse({"recommendations": product_titles})


# -------------------------
# Upsell suggestions (by product_id)
# -------------------------
def upsell_recommendations_api(request, product_id):
    try:
        base = Item.objects.get(id=product_id)
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Product not found.'}, status=404)

    # Suggest higher-tier (recent) products in same category
    upsells = Item.objects.filter(category=base.category).exclude(id=base.id).order_by("-created_at")[:4]
    return JsonResponse({"product": base.title, "upsell_suggestions": [p.title for p in upsells]})


# -------------------------
# Cross-sell suggestions (by customer)
# -------------------------
def cross_sell_recommendations_api(request, customer_id):
    invoices = TaxInvoice.objects.filter(customer_id=customer_id)
    if not invoices.exists():
        return JsonResponse({'cross_sell_suggestions': []})

    purchased_product_ids = TaxInvoiceItem.objects.filter(invoice__in=invoices).values_list("product_id", flat=True)

    co_purchased = (TaxInvoiceItem.objects
                    .exclude(product_id__in=purchased_product_ids)
                    .values("product_id")
                    .annotate(cnt=Count("product_id"))
                    .order_by("-cnt")[:6])

    titles = []
    for entry in co_purchased:
        pid = entry["product_id"]
        item = Item.objects.filter(id=pid).first()
        if item:
            titles.append(item.title)
        else:
            titles.append(f"Product-{pid}")

    return JsonResponse({"cross_sell_suggestions": titles})


# -------------------------
# Message generation (simple)
# -------------------------
@csrf_exempt
def generate_message_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    try:
        data = json.loads(request.body)
        customer = data.get("customer_name")
        base = data.get("base_product")
        recommended = data.get("recommended_product")
        rec_type = data.get("recommendation_type", "recommendation")
        if not all([customer, base, recommended]):
            return JsonResponse({"error": "Missing required fields."}, status=400)

        message = f"Hello {customer}, since you had {base}, we recommend {recommended}. ({rec_type})"
        return JsonResponse({"message": message})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -------------------------
# Send message via RAP Booster
# -------------------------
@csrf_exempt
def send_message_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        customer_name = data.get("customer_name")
        customer_number = data.get("customer_number")
        message = data.get("message")

        if not all([customer_name, customer_number, message]):
            return JsonResponse({"error": "customer_name, customer_number, message required."}, status=400)

        payload = {
            "apikey": RAPBOOSTER_API_KEY,
            "mobile": str(customer_number),
            "msg": message
        }

        response = requests.post(RAPBOOSTER_API_URL, data=payload, timeout=15)
        try:
            result = response.json() if response.text else {"status": "no response"}
        except:
            result = {"status": "invalid json from provider", "text": response.text}

        if response.status_code == 200:
            return JsonResponse({"status": "success", "response": result})
        else:
            return JsonResponse({"status": "failed", "response": result}, status=500)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# recommender/views_api.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .ml.ml_service import get_recommendations


@csrf_exempt
def api_get_recommendations(request, customer_id):
    """
    Main production API for recommendation system.
    Input: customer_id (int)
    Output: JSON response with recommended products.
    """

    try:
        customer_id = int(customer_id)
    except:
        return JsonResponse({
            "status": "error",
            "message": "Invalid customer_id."
        }, status=400)

    # Call ML engine
    result = get_recommendations(customer_id)

    # If engine failed
    if result.get("status") == "error":
        return JsonResponse(result, status=500)

    # Successful output
    return JsonResponse({
        "status": "success",
        "customer_id": customer_id,
        "recommendations": result.get("recommendations", []),
        "message": result.get("message", "")
    }, status=200)
