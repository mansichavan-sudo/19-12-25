from .rapbooster_api import send_whatsapp_message, send_email_message
from crmapp.models import customer_details
from .engine import generate_recommendations


def send_recommendations_to_customer(customer_id):

    # 1. Load customer
    customer = customer_details.objects.filter(id=customer_id).first()
    if not customer:
        return {"status": "error", "msg": "Customer not found"}

    # 2. Generate recommendations
    result = generate_recommendations(customer_id)
    items = result.get("recommendations", [])

    if not items:
        return {"status": "ok", "msg": "No recommendations found"}

    # 3. Format message
    item_list = "\n".join([f"• {p}" for p in items])
    message = f"Hello {customer.fullname},\nBased on your past interest we recommend:\n\n{item_list}"

    email_subject = "Your Personalized Product Recommendations"

    # 4. Send WhatsApp
    w_status, w_resp = send_whatsapp_message(customer.primarycontact, message, customer)

    # 5. Send Email
    if customer.primaryemail:
        e_status, e_resp = send_email_message(customer.primaryemail, email_subject, message)
    else:
        e_status, e_resp = "skipped", "No email available"

    # 6. Return final result
    return {
        "status": "sent",
        "customer": customer.fullname,
        "whatsapp_status": w_status,
        "email_status": e_status,
        "recommendations": items
    }
