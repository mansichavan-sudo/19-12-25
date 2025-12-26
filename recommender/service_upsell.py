from crmapp.models import service_management
from datetime import date


# -------------------------
# Normalization helpers
# -------------------------

def warranty_to_months(warranty):
    if not warranty:
        return 0

    w = warranty.lower().strip()

    if w in ["0", "o", "na", "single"]:
        return 0

    if "month" in w:
        try:
            return int(w.split()[0])
        except:
            return 0

    if "year" in w:
        try:
            return int(w.split()[0]) * 12
        except:
            return 12

    try:
        return int(w)
    except:
        return 0


def frequency_to_count(freq):
    if not freq:
        return 1

    f = freq.lower().strip()

    if f == "fortnight":
        return 2

    try:
        return int(f)
    except:
        return 1


# -------------------------
# MAIN UPSSELL FUNCTION
# -------------------------

def service_upsell_rules(customer_id, top_n=3):
    """
    Service Upsell Rules:
    1) Low warranty → renewal / AMC
    2) Low frequency → higher frequency
    3) One-time → AMC conversion
    """

    services = service_management.objects.filter(
        customer_id=customer_id,
        contract_status="Completed"
    )

    recommendations = []
    seen = set()

    for svc in services:
        warranty_months = warranty_to_months(svc.warranty_period)
        frequency = frequency_to_count(svc.frequency_count)

        key = (svc.service_subject, svc.contract_type)

        # -------------------------
        # Rule 1: Warranty expiring
        # -------------------------
        if warranty_months <= 3:
            rec_key = (svc.service_subject, "AMC Renewal")
            if rec_key not in seen:
                recommendations.append({
                    "type": "service_upsell",
                    "service_subject": svc.service_subject,
                    "recommended_service": "Annual Maintenance Contract (AMC)",
                    "reason": "Warranty expiring soon",
                    "score": 0.90
                })
                seen.add(rec_key)

        # -------------------------
        # Rule 2: Frequency upgrade
        # -------------------------
        if frequency <= 1:
            rec_key = (svc.service_subject, "High Frequency")
            if rec_key not in seen:
                recommendations.append({
                    "type": "service_upsell",
                    "service_subject": svc.service_subject,
                    "recommended_service": "Higher Frequency Service",
                    "reason": "Low service frequency",
                    "score": 0.78
                })
                seen.add(rec_key)

        # -------------------------
        # Rule 3: One-time → AMC
        # -------------------------
        if svc.contract_type.lower() == "one time":
            rec_key = (svc.service_subject, "AMC Conversion")
            if rec_key not in seen:
                recommendations.append({
                    "type": "service_upsell",
                    "service_subject": svc.service_subject,
                    "recommended_service": "AMC Plan",
                    "reason": "One-time service detected",
                    "score": 0.85
                })
                seen.add(rec_key)

    return sorted(
        recommendations,
        key=lambda x: x["score"],
        reverse=True
    )[:top_n]
