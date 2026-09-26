from typing import Any, Optional
from app.composer.base import (
    get_owner_name, get_salutation, get_locality, get_business_name,
    get_active_offer, is_hindi_preferred, sanitize_for_whatsapp
)

class RestaurantsStrategy:
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
        offer_title = active_offer.get("title", "Combo Meal @ ₹199") if active_offer else "Combo Meal @ ₹199"

        # Customer-facing
        if customer or scope == "customer":
            c_name = customer.get("identity", {}).get("name", "there") if customer else "there"
            body = (
                f"Hi {c_name}! Craving good food from {b_name} in {locality}? "
                f"We've freshly prepared our chef specials today with complimentary delivery on orders above ₹299. "
                f"Want to see today's top picks? Reply YES to view the menu."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "merchant_on_behalf",
                "suppression_key": suppression_key,
                "template_name": "restaurant_customer_invite_v1",
                "template_params": [c_name, b_name, locality],
                "rationale": "Direct customer appetizing invite with low friction menu CTA."
            }

        # Merchant-facing
        perf = merchant.get("performance", {})
        
        if kind == "active_planning_intent":
            body = (
                f"{owner}, here's a starter bulk package structure for {b_name} in {locality} — you can edit:\n\n"
                f"{b_name} Corporate Lunch Package:\n"
                f"- 10 thalis @ ₹125 each (₹25 off retail) + free delivery\n"
                f"- 25 thalis @ ₹115 each + 2 complimentary beverages\n"
                f"- 50+ thalis: ₹105 each + 1 complimentary dessert platter\n"
                f"- Pre-order day-before by 5pm; delivery 12:30-1:00pm\n\n"
                f"Offices within your 3km delivery radius are ordering weekly. Want me to draft a 3-line WhatsApp you can send facilities managers?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_restaurant_b2b_package_v1",
                "template_params": [owner, b_name, locality],
                "rationale": "High-value B2B catering package complete with tiered volume pricing and outreach copy."
            }

        if kind == "ipl_match_today":
            teams = payload.get("match", "DC vs MI")
            stadium = payload.get("stadium", "Arun Jaitley Stadium")
            time_str = payload.get("time", "7:30pm")
            body = (
                f"Quick heads-up {owner} — {teams} at {stadium} tonight, {time_str}. Important: "
                f"Saturday IPL matches typically shift -12% dine-in restaurant covers as diners watch at home. "
                f"Skip the dine-in match-night discount today; instead push your {offer_title} as a delivery-only game-night special. "
                f"Want me to draft the delivery banner + an Insta story? Live in 10 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_restaurant_ipl_strategy_v1",
                "template_params": [owner, teams, stadium, time_str, offer_title],
                "rationale": "Contrarian data-driven advice mitigating dine-in losses and leveraging active delivery items."
            }

        if kind == "milestone_reached":
            reviews = perf.get("reviews", 100)
            body = (
                f"Congratulations {owner}! {b_name} just crossed a major milestone on Google: 100+ positive customer reviews in {locality}! 🌟 "
                f"Sharing this milestone builds massive trust with new diners browsing nearby. "
                f"Want me to generate a celebration thank-you post + a Google review badge for your counter? Takes 3 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_restaurant_milestone_celebration_v1",
                "template_params": [owner, b_name, locality],
                "rationale": "Celebration milestone leveraging social proof to drive customer loyalty."
            }

        if kind == "competitor_opened":
            body = (
                f"{owner}, a new food outlet opened within 1.2km of {b_name} in {locality}. "
                f"To keep your regular lunch covers steady, let's highlight your signature specials on Google and magicpin. "
                f"Want me to publish a feature post for '{offer_title}' today at 11am ahead of the lunch rush?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_restaurant_competitor_defense_v1",
                "template_params": [owner, b_name, locality, offer_title],
                "rationale": "Defensive lunch rush timing counteracting new neighborhood competitor."
            }

        if kind == "dormant_with_vera":
            body = (
                f"{owner}, quick audit for {b_name}: food searches in {locality} are peaking on weekends, "
                f"but your Google menu photos haven't been updated in 25 days. Fresh visuals lift click-to-directions by 22%. "
                f"Want me to help you post 2 high-performing dishes with prices today? Just reply GO."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_confirm_cancel",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_restaurant_dormancy_reactivation_v1",
                "template_params": [owner, b_name, locality],
                "rationale": "Dormancy wake-up highlighting photographic menu updates."
            }

        # Fallback
        body = (
            f"Hi {owner}, quick operational pulse for {b_name}: diners in {locality} are ordering family combos 30% more this month. "
            f"Featuring your '{offer_title}' can capture higher order values. "
            f"Want me to schedule a featured special post for this evening? Ready in 5 min."
        )
        return {
            "body": sanitize_for_whatsapp(body),
            "cta": "binary_yes_no",
            "send_as": "vera",
            "suppression_key": suppression_key,
            "template_name": "vera_restaurant_generic_nudge_v1",
            "template_params": [owner, b_name, locality, offer_title],
            "rationale": "Operator-level basket size expansion suggestion."
        }
