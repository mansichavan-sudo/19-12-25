def compose_prompt(customer_name, channel, recommendations):
    services = []
    products = []

    for r in recommendations:
        if r["service_name"]:
            services.append(r["service_name"])
        if r["product_name"]:
            products.append(r["product_name"])

    services_text = ", ".join(set(services)) if services else "no services"
    products_text = ", ".join(set(products)) if products else "no products"

    if channel == "whatsapp":
        tone = "short, friendly, WhatsApp style"
    elif channel == "email":
        tone = "professional email format"
    else:
        tone = "sales call script"

    return f"""
You are a CRM assistant.

Customer name: {customer_name}
Channel: {channel}

Recommended services:
{services_text}

Recommended products:
{products_text}

Write a {tone} message including the customer name.
"""
