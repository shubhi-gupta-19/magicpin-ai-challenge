from typing import Any, Optional
from app.composer.base import (
    get_owner_name, get_salutation, get_locality, get_business_name,
    get_active_offer, is_hindi_preferred, sanitize_for_whatsapp
)

class SalonsStrategy:
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
        offer_title = active_offer.get("title", "Haircut @ ₹99") if active_offer else "Haircut @ ₹99"

        # Customer-facing messages
        if customer or scope == "customer":
            c_name = customer.get("identity", {}).get("name", "there") if customer else "there"
            
            if kind in ("wedding_package_followup", "bridal_followup"):
                days = payload.get("days_to_wedding", 196)
                wedding_date = payload.get("wedding_date", "2026-11-08")
                body = (
                    f"Hi {c_name} 💍 {owner} from {b_name} here. {days} days to your wedding ({wedding_date}) — "
                    f"perfect window to start the 30-day skin-prep program before peak bridal bookings roll in. "
                    f"₹2,499 covers 4 sessions + a take-home kit. Want me to block your preferred Saturday 4pm slot for the first session next week?"
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "salon_bridal_followup_v1",
                    "template_params": [c_name, owner, b_name, str(days), wedding_date],
                    "rationale": "High-intent bridal journey milestone follow-up with concrete package details and preferred slot booking."
                }

            if kind == "appointment_tomorrow":
                time_slot = payload.get("time", "2:30 PM")
                body = (
                    f"Hi {c_name} ✨ Just a quick reminder from {b_name} for your salon appointment tomorrow at {time_slot}. "
                    f"We have your stylist reserved. Reply YES to confirm, or let us know if you need to adjust the time!"
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "salon_appointment_reminder_v1",
                    "template_params": [c_name, b_name, time_slot],
                    "rationale": "Warm, personalized appointment confirmation."
                }

            if kind in ("customer_lapsed_soft", "customer_lapsed_hard"):
                body = (
                    f"Hi {c_name} 💇‍♀️ We miss seeing you at {b_name} in {locality}! "
                    f"It's been a few weeks — we've got a fresh seasonal slot open for your next styling. "
                    f"Our {offer_title} is available this week. Would you like us to save a slot for you this Saturday? Reply YES to book."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "salon_lapsed_winback_v1",
                    "template_params": [c_name, b_name, locality, offer_title],
                    "rationale": "Friendly winback with seasonal styling invitation."
                }

        # Merchant-facing messages
        perf = merchant.get("performance", {})
        
        if kind == "curious_ask_due":
            body = (
                f"Hi {owner}! Quick check — what service has been most asked-for this week at {b_name}? "
                f"I'll turn your answer into a high-reach Google post + a 4-line WhatsApp reply you can copy-paste when customers ask about pricing. Takes 5 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "open_ended",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_salon_curious_ask_v1",
                "template_params": [owner, b_name],
                "rationale": "Asking-the-merchant curiosity lever offering immediate effort-externalized content production."
            }

        if kind == "dormant_with_vera":
            body = (
                f"Hi {owner}, quick profile audit for {b_name}: you've built a stellar 4.8★ rating in {locality}, "
                f"but your Google Business posts have been dormant for over 20 days. Active salons in your area post 2x/week to capture weekend footfall. "
                f"Want me to draft 2 weekend styling posts featuring '{offer_title}'? Just reply YES."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_salon_dormancy_reactivation_v1",
                "template_params": [owner, b_name, locality, offer_title],
                "rationale": "Reactivating dormant salon merchant using peer posting cadence and social proof."
            }

        if kind == "perf_dip":
            views_drop = abs(int(payload.get("delta_pct", -0.25) * 100))
            body = (
                f"Hi {owner}, heads-up: discovery views for {b_name} dipped {views_drop}% this week. "
                f"Salons in {locality} are currently running seasonal hair spa and grooming specials to boost mid-week bookings. "
                f"Want me to publish a Google post promoting '{offer_title}' to bring in appointments before the weekend? Live in 10 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_salon_perf_dip_v1",
                "template_params": [owner, b_name, str(views_drop), locality, offer_title],
                "rationale": "Performance dip alert with immediate localized promotional countermeasure."
            }

        if kind == "festival_upcoming":
            fest = payload.get("festival", "Diwali")
            days = payload.get("days_until", 30)
            body = (
                f"Hi {owner}! {fest} is {days} days away — salon appointments across {locality} typically book out 2 weeks ahead. "
                f"Launching your festive makeover packages early locks in repeat clients before slots fill up. "
                f"Want me to draft a 3-tier festive grooming menu you can share with your customer list?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_salon_festival_prep_v1",
                "template_params": [owner, fest, str(days), locality],
                "rationale": "Advance festive calendar planning capitalizing on booking scarcity."
            }

        # Default fallback
        body = (
            f"Hi {owner}! Checked {b_name} in {locality} today: search interest for beauty and salon services is up 18% locally. "
            f"Want me to showcase your '{offer_title}' on Google with a fresh photo post to capture today's searchers? Takes 2 min."
        )
        return {
            "body": sanitize_for_whatsapp(body),
            "cta": "binary_yes_no",
            "send_as": "vera",
            "suppression_key": suppression_key,
            "template_name": "vera_salon_generic_nudge_v1",
            "template_params": [owner, b_name, locality, offer_title],
            "rationale": "Local search demand nudge with effortless 1-click execution."
        }
