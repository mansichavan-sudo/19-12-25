# recommender/service_rules.py

from crmapp.models import service_management

def service_upsell_rules(customer_id):
    services = service_management.objects.filter(
        customer_id=customer_id,
        contract_status="Completed"
    )

    recs = set()

    for s in services:
        if s.contract_type == "AMC":
            recs.add("Extended Warranty")

        if s.frequency_count in ["1", "2"]:
            recs.add("Higher Frequency Plan")

        if s.property_type == "Commercial":
            recs.add("Annual Contract")

    return list(recs)
