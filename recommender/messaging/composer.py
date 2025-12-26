def _build_block(title, items, show_confidence=False):
    """
    Builds a formatted message block.
    """
    if not items:
        return ""

    lines = [title]
    for item in items:
        if show_confidence and item.get("confidence") is not None:
            score = int(float(item["confidence"]) * 100)
            lines.append(f"• {item['name']} ({score}% match)")
        else:
            lines.append(f"• {item['name']}")

    return "\n".join(lines)


def compose_message(customer, recommendations, channel="whatsapp"):
    """
    Central message composition engine.
    """

    first_name = customer.fullname.split(" ")[0]

    # Merge products + services
    upsell_items = (
        recommendations["upsell"]["products"]
        + recommendations["upsell"]["services"]
    )

    cross_sell_items = (
        recommendations["cross_sell"]["products"]
        + recommendations["cross_sell"]["services"]
    )

    # Channel-specific tone
    if channel == "email":
        upsell_title = "Recommended Upgrade Options"
        cross_title = "Additional Services & Products You May Like"
        cta = "Please reply to this email to proceed or contact us for details."
        greeting = f"Dear {customer.fullname},"
        signature = "Regards,\nTEIM Pest Control Team"

    else:  # WhatsApp / SMS
        upsell_title = "🔼 Recommended Upgrades"
        cross_title = "🛒 Additional Recommendations"
        cta = "Reply YES to proceed or HELP to talk to our expert."
        greeting = f"Hi {first_name} 👋"
        signature = "— TEIM Pest Control AI"

    upsell_block = _build_block(
        upsell_title,
        upsell_items,
        show_confidence=(channel == "email")
    )

    cross_sell_block = _build_block(
        cross_title,
        cross_sell_items
    )

    # Remove empty blocks automatically
    body_parts = [
        greeting,
        "",
        "Based on your service history, our AI recommends:",
        "",
        upsell_block,
        "",
        cross_sell_block,
        "",
        cta,
        "",
        signature
    ]

    final_message = "\n".join(
        part for part in body_parts if part.strip()
    )

    return final_message.strip()
