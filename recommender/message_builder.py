def build_recommendation_message(customer, recommendations):
    first_name = customer.fullname.split(" ")[0]

    upsell_products, upsell_services = [], []
    crosssell_products, crosssell_services = [], []

    for r in recommendations:
        intent = r.business_intent or r.recommendation_type

        # PRODUCT
        if r.reco_channel == "product" and r.recommended_product:
            line = f"• {r.recommended_product.product_name}"

            if intent == "upsell":
                upsell_products.append(line)
            elif intent == "crosssell":
                crosssell_products.append(line)

        # SERVICE
        elif r.reco_channel == "service" and r.recommended_service:
            line = f"• {r.recommended_service.service_name}"

            if intent == "upsell":
                upsell_services.append(line)
            elif intent == "crosssell":
                crosssell_services.append(line)

    sections = []

    if upsell_products:
        sections.append(
            "🔥 Recommended Product Upgrades:\n" +
            "\n".join(upsell_products[:3])
        )

    if upsell_services:
        sections.append(
            "🛠 Recommended Service Upgrades:\n" +
            "\n".join(upsell_services[:3])
        )

    if crosssell_products:
        sections.append(
            "➕ Additional Products You May Need:\n" +
            "\n".join(crosssell_products[:3])
        )

    if crosssell_services:
        sections.append(
            "📦 Additional Services You May Need:\n" +
            "\n".join(crosssell_services[:3])
        )

    if not sections:
        return None

    message_body = "\n\n".join(sections)

    return f"""Hi {first_name},

Based on your pest history and recent activity, our AI recommends:

{message_body}

Reply YES to book or HELP to talk to our expert.
— TEIM Pest Control AI
""".strip()
