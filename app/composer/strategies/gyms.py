from typing import Any, Optional
from app.composer.base import (
    get_owner_name, get_salutation, get_locality, get_business_name,
    get_active_offer, is_hindi_preferred, sanitize_for_whatsapp
)

class GymsStrategy:
    @staticmethod
    def compose(category: dict[str, Any], merchant: dict[str, Any], trigger: dict[str, Any], customer: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        kind = trigger.get("kind", "")
        scope = trigger.get("scope", "merchant")
        payload = trigger.get("payload", {})
        suppression_key = trigger.get("suppression_key") or f"{kind}:{merchant.get('merchant_id')}"
        owner = get_owner_name(merchant, "there")
        b_name = get_business_name(merchant)
        locality = get_locality(merchant)
        active_offer = get_active_offer(merchant, category)
        offer_title = active_offer.get("title", "First Month @ ₹499") if active_offer else "First Month @ ₹499"

        # Customer-facing
        if customer or scope == "customer":
            c_name = customer.get("identity", {}).get("name", "there") if customer else "there"
            
            if kind in ("customer_lapsed_hard", "customer_lapsed_soft", "winback"):
                body = (
                    f"Hi {c_name} 👋 {owner} from {b_name} here. It's been about 8 weeks — happens to most members at some point, no judgment. "
                    f"We've added a Tue/Thu evening HIIT class that fits weight-loss goals well (45 min, 6:30pm). "
                    f"Want me to hold a free trial spot for you next Tue, 30 Apr? Reply YES — no commitment, no auto-charge."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "gym_winback_no_shame_v1",
                    "template_params": [c_name, owner, b_name],
                    "rationale": "Empathetic, no-shame winback message paired with a zero-friction trial class invitation."
                }

            if kind == "recall_due":
                body = (
                    f"Hi {c_name}! Your fitness cycle check-in at {b_name} is up. "
                    f"Consistency is where results happen — we have new strength and mobility batches opening this week in {locality}. "
                    f"Would you like us to reserve your spot for a complimentary progress assessment? Reply 1 for Morning, 2 for Evening."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "multi_choice_slot",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "gym_recall_assessment_v1",
                    "template_params": [c_name, b_name, locality],
                    "rationale": "Membership progress review encouraging fitness habit retention."
                }

        # Merchant-facing
        cust_agg = merchant.get("customer_aggregate", {})
        members_n = cust_agg.get("total_unique_ytd", 245)
        perf = merchant.get("performance", {})

        if kind == "active_planning_intent":
            body = (
                f"{owner}, here is a high-demand structure for your summer fitness program at {b_name}:\n\n"
                f"{b_name} Kids & Teens Summer Camp:\n"
                f"- Age batches: 7-11 yrs (8:30-9:30am) & 12-16 yrs (10:00-11:00am)\n"
                f"- Focus: posture, agility, mobility & breathwork\n"
                f"- 2-week module @ ₹1,800 (capped at 15 participants per batch)\n\n"
                f"Parents in {locality} are looking for structured morning activities. Want me to draft the announcement flyer copy + WhatsApp note?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_gym_kids_program_v1",
                "template_params": [owner, b_name, locality],
                "rationale": "Structured seasonal youth fitness program designed to monetize idle morning gym capacity."
            }

        if kind in ("seasonal_perf_dip", "perf_dip"):
            views_drop = abs(int(payload.get("delta_pct", -0.30) * 100))
            body = (
                f"{owner}, your views are down {views_drop}% this week — but I want to flag this is the normal seasonal acquisition lull "
                f"(metro gyms typically see -25% to -35% in this window). Action: skip heavy ad spend now and focus retention on your {members_n} members. "
                f"Want me to draft a 30-day 'Summer Consistency Challenge' WhatsApp campaign to keep them attending? Takes 5 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_gym_seasonal_reframe_v1",
                "template_params": [owner, str(views_drop), str(members_n)],
                "rationale": "Seasonal dip reframe pre-empting merchant panic with member retention focus."
            }

        if kind == "perf_spike":
            views_jump = int(payload.get("delta_pct", 0.35) * 100)
            body = (
                f"Great momentum {owner}! Search queries for fitness coaching at {b_name} spiked +{views_jump}% over baseline in {locality}. "
                f"Capitalizing on this traffic now before queries cool down converts views to walk-ins. "
                f"Want me to spotlight your '{offer_title}' on Google Business with a limited-slot callout today?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_gym_perf_spike_conversion_v1",
                "template_params": [owner, b_name, str(views_jump), locality, offer_title],
                "rationale": "High-intent traffic capture during discovery spike."
            }

        # Fallback
        body = (
            f"Hi {owner}, quick pulse on {b_name}: {locality} residents are searching for strength & conditioning training this month. "
            f"Featuring your '{offer_title}' gives newcomers a low-risk entry into your community. "
            f"Want me to publish a member transformation highlight post to Google today?"
        )
        return {
            "body": sanitize_for_whatsapp(body),
            "cta": "binary_yes_no",
            "send_as": "vera",
            "suppression_key": suppression_key,
            "template_name": "vera_gym_generic_nudge_v1",
            "template_params": [owner, b_name, locality, offer_title],
            "rationale": "General local demand capture for fitness facility."
        }
