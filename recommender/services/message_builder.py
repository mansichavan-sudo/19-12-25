class MessageBuilder:

    @staticmethod
    def build(customer, recommendations, channel="whatsapp"):
        first_name = customer.fullname.split(" ")[0]

        upsell = recommendations.get("upsell", {})
        cross_sell = recommendations.get("cross_sell", {})

        sections = []

        # 🔥 Upsell Products
        if upsell.get("products"):
            sections.append(
                "🔥 Recommended Product Upgrades:\n" +
                "\n".join(
                    f"• {p['name']}" for p in upsell["products"][:3]
                )
            )

        # 🛠 Upsell Services
        if upsell.get("services"):
            sections.append(
                "🛠 Recommended Service Upgrades:\n" +
                "\n".join(
                    f"• {s['name']}" for s in upsell["services"][:3]
                )
            )

        # ➕ Cross-sell Products
        if cross_sell.get("products"):
            sections.append(
                "➕ Additional Products You May Need:\n" +
                "\n".join(
                    f"• {p['name']}" for p in cross_sell["products"][:3]
                )
            )

        # 📦 Cross-sell Services
        if cross_sell.get("services"):
            sections.append(
                "📦 Additional Services You May Need:\n" +
                "\n".join(
                    f"• {s['name']}" for s in cross_sell["services"][:3]
                )
            )

        if not sections:
            return None

        body = "\n\n".join(sections)

        # ✉️ Email vs WhatsApp
        if channel == "email":
            return f"""Dear {first_name},

Based on your pest history and recent activity, our system recommends:

{body}

Regards,
TEIM Pest Control
""".strip()

        # 📱 WhatsApp (default)
        return f"""Hi {first_name} 👋

Based on your pest history and recent activity, our AI recommends:

{body}

Reply YES to book or HELP to talk to our expert.
— TEIM Pest Control AI
""".strip()
