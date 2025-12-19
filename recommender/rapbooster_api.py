import requests
import os
from django.conf import settings

from crmapp.models import SentMessageLog, customer_details


# ====================================================================
#   RAPBOOSTER PRODUCTION CONFIG
# ====================================================================

WHATSAPP_API = "https://rapbooster.ai/api/send_whatsapp/"
EMAIL_API = "https://rapbooster.ai/api/send_email/"

# Prefer Django settings env var → fallback to OS environment → fallback to hardcoded key
API_KEY = getattr(settings, "RAPBOOSTER_API_KEY", None) or \
          os.getenv("RAPBOOSTER_API_KEY") or \
          "6538c8eff027d41e9151"


# ====================================================================
#   UNIVERSAL MESSAGE LOGGER
# ====================================================================

def create_log(customer, recipient, channel, subject, body, status, provider_response, message_id=None):
    """
    Stores WhatsApp and Email logs.
    """

    return SentMessageLog.objects.create(
        customer=customer,
        recipient=recipient,
        channel=channel,
        rendered_subject=subject,
        rendered_body=body,
        status=status,
        provider_response=provider_response,
        message_id=message_id
    )


# ====================================================================
#   WHATSAPP SENDER — CLEAN & PRODUCTION READY
# ====================================================================

def send_whatsapp_message(phone: str, message: str, customer: customer_details = None):
    """
    Sends WhatsApp message using RapBooster API with logging.
    """

    phone = str(phone).strip()

    # Auto-attach customer if not passed
    if customer is None:
        customer = customer_details.objects.filter(primarycontact=phone).first()

    if not customer:
        return "error", f"Customer not found for phone: {phone}"

    # Create queue log
    log = create_log(
        customer=customer,
        recipient=phone,
        channel="whatsapp",
        subject="",
        body=message,
        status="queued",
        provider_response=""
    )

    payload = {
        "apikey": API_KEY,
        "phone": phone,
        "message": message,
        "customer_name": customer.fullname
    }

    try:
        response = requests.post(WHATSAPP_API, json=payload, timeout=10)
        resp_text = response.text

        # Safe JSON decode
        try:
            resp_json = response.json()
        except:
            resp_json = {}

        # RapBooster message id
        message_id = resp_json.get("message_id") or resp_json.get("id")

        success = response.status_code == 200 and resp_json.get("status") in ["success", "sent"]

        log.status = "sent" if success else "failed"
        log.provider_response = resp_text
        log.message_id = message_id
        log.save()

        return log.status, resp_text

    except Exception as e:
        log.status = "error"
        log.provider_response = str(e)
        log.save()
        return "error", str(e)


# ====================================================================
#   EMAIL SENDER — CLEAN & PRODUCTION READY
# ====================================================================

def send_email_message(email: str, subject: str, message: str):
    """
    Sends Email via RapBooster API.
    """

    customer = customer_details.objects.filter(primaryemail=email).first()

    if not customer:
        return "error", f"Customer not found for email: {email}"

    # Create queued log
    log = create_log(
        customer=customer,
        recipient=email,
        channel="email",
        subject=subject,
        body=message,
        status="queued",
        provider_response=""
    )

    payload = {
        "apikey": API_KEY,
        "email": email,
        "subject": subject,
        "message": message,
        "customer_name": customer.fullname
    }

    try:
        response = requests.post(EMAIL_API, json=payload, timeout=10)
        resp_text = response.text

        try:
            resp_json = response.json()
        except:
            resp_json = {}

        message_id = resp_json.get("message_id") or resp_json.get("id")

        success = response.status_code == 200 and resp_json.get("status") in ["success", "sent"]

        log.status = "sent" if success else "failed"
        log.provider_response = resp_text
        log.message_id = message_id
        log.save()

        return log.status, resp_text

    except Exception as e:
        log.status = "error"
        log.provider_response = str(e)
        log.save()
        return "error", str(e)


# ====================================================================
#   RECOMMENDATION SHORTCUT
# ====================================================================

def send_recommendation_message(customer: customer_details, message: str):
    """
    Sends recommendation to customer's WhatsApp.
    """
    return send_whatsapp_message(customer.primarycontact, message, customer)
