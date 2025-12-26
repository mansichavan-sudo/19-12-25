def format_items(items):
    """
    Convert list of products/services to bullet string
    """
    if not items:
        return "• None at the moment"

    return "\n".join([f"• {item['name']}" for item in items])


def render_message(template_body, customer, recommendations):
    """
    Render final message body using model output
    """

    upsell = recommendations.get("upsell", {})
    crosssell = recommendations.get("crosssell", {})

    context = {
        "{{customer_name}}": customer.name,

        "{{upsell_products}}": format_items(upsell.get("products", [])),
        "{{upsell_services}}": format_items(upsell.get("services", [])),

        "{{crosssell_products}}": format_items(crosssell.get("products", [])),
        "{{crosssell_services}}": format_items(crosssell.get("services", [])),
    }

    message = template_body
    for key, value in context.items():
        message = message.replace(key, value)

    return message
