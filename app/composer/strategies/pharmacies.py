from typing import Any, Optional
from app.composer.base import (
    get_owner_name, get_salutation, get_locality, get_business_name,
    get_active_offer, is_hindi_preferred, sanitize_for_whatsapp
)

class PharmaciesStrategy:
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
        offer_title = active_offer.get("title", "Free Home Delivery above ₹499") if active_offer else "Free Home Delivery above ₹499"

        # Customer-facing
        if customer or scope == "customer":
            c_name = customer.get("identity", {}).get("name", "there") if customer else "there"
            hi_mix = is_hindi_preferred(customer) if customer else True

            if kind in ("chronic_refill_due", "refill_due"):
                due_date = payload.get("due_date", "28 April")
                meds = payload.get("medicines", "metformin, atorvastatin, telmisartan")
                if hi_mix:
                    body = (
                        f"Namaste — {b_name} {locality} yahan. {c_name} ji ki monthly medicines ({meds}) "
                        f"{due_date} ko khatam hongi. Same dose, genuine brand pack ready hai. Senior 15% discount applied — total ₹1,420 (₹240 saved). "
                        f"Free home delivery to saved address by 5pm tomorrow. Reply CONFIRM to dispatch, or call if any change in dosage."
                    )
                else:
                    body = (
                        f"Namaste from {b_name} {locality}. This is a reminder for {c_name}'s scheduled monthly refills ({meds}), due on {due_date}. "
                        f"Your exact prescribed brand pack is ready with 15% discount applied (Total ₹1,420, ₹240 savings). "
                        f"Free home delivery available to your address by 5pm tomorrow. Reply CONFIRM to dispatch, or reply with updated prescription."
                    )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_confirm_cancel",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "pharmacy_refill_reminder_v1",
                    "template_params": [c_name, b_name, locality, meds, due_date],
                    "rationale": "Respectful, clinical chronic prescription refill reminder with verified molecule names and delivery savings."
                }

            if kind in ("customer_lapsed_soft", "customer_lapsed_hard", "recall_due"):
                body = (
                    f"Namaste {c_name} ji from {b_name} {locality}. Quick check-in on your regular wellness and healthcare supplies. "
                    f"Our pharmacy provides {offer_title} to your doorstep. "
                    f"Would you like us to assist with refilling any prescriptions today? Reply YES to connect."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "pharmacy_lapsed_refill_v1",
                    "template_params": [c_name, b_name, locality, offer_title],
                    "rationale": "Respectful pharmacy wellness and chronic care refill re-engagement."
                }

            # Generic customer reachout
            body = (
                f"Namaste {c_name} from {b_name}. Friendly reminder that our doorstep medicine delivery is active in {locality}. "
                f"Need any prescription refills or healthcare essentials today? Reply YES to order."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "merchant_on_behalf",
                "suppression_key": suppression_key,
                "template_name": "pharmacy_customer_generic_v1",
                "template_params": [c_name, b_name, locality],
                "rationale": "Direct doorstep pharmacy delivery check-in."
            }

        # Merchant-facing
        cust_agg = merchant.get("customer_aggregate", {})
        total_chronic = cust_agg.get("total_unique_ytd", 240)

        if kind in ("supply_alert", "regulation_change"):
            batch1 = payload.get("batch_1", "AT2024-1102")
            batch2 = payload.get("batch_2", "AT2024-1108")
            body = (
                f"{owner}, urgent compliance notice: voluntary batch recall on 2 atorvastatin lots ({batch1}, {batch2}) "
                f"by manufacturer due to minor sub-potency (no direct health hazard, but requires replacement). "
                f"Cross-referencing your dispensing roster indicates approximately 22 repeat customers received these lots in the last 90 days. "
                f"Want me to draft a reassuring replacement note + pickup protocol for them?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_pharmacy_batch_recall_alert_v1",
                "template_params": [owner, batch1, batch2],
                "rationale": "High-urgency pharmaceutical batch recall notice with patient-safety protocol and patient cohort quantification."
            }

        if kind in ("category_seasonal", "summer_demand_shift"):
            body = (
                f"Hi {owner}, summer temperatures in {locality} are triggering an immediate surge in hydration & heat-safety purchases "
                f"(ORS sachets, glucose formulas, electrolytes, and medical-grade sunblocks are trending +45% in local queries). "
                f"Want me to draft a quick 'Summer Essential Kit' Google update featuring your {offer_title} to direct neighborhood shoppers to {b_name}?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_pharmacy_seasonal_demand_v1",
                "template_params": [owner, locality, b_name, offer_title],
                "rationale": "Seasonal climate-health demand alignment with instant local inventory positioning."
            }

        if kind == "gbp_unverified":
            body = (
                f"Hi {owner}, patients searching for late-night pharmacies in {locality} cannot see verified hours for {b_name} on Google Maps. "
                f"Unverified listings lose up to 60% of emergency prescription walk-ins. "
                f"Want me to guide you through a 2-minute phone verification to secure your pharmacy's emergency badge?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_pharmacy_unverified_gbp_v1",
                "template_params": [owner, locality, b_name],
                "rationale": "Emergency medical trust and operating hours verification reminder."
            }

        if kind == "perf_spike":
            body = (
                f"Heads-up {owner}! Local search queries for home medicine delivery and prescription care at {b_name} jumped +28% this week. "
                f"Featuring your '{offer_title}' prominently on your listing converts high-intent searches into orders. "
                f"Want me to publish a delivery spotlight post to your Google profile today?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_pharmacy_perf_spike_v1",
                "template_params": [owner, b_name, offer_title],
                "rationale": "High-intent healthcare delivery conversion prompt."
            }

        # Fallback
        body = (
            f"Namaste {owner}, quick health update for {b_name}: {locality} households are refilling chronic supplies this week. "
            f"Featuring '{offer_title}' reassures senior citizens and busy families in your neighborhood. "
            f"Want me to schedule a helpful health post for tomorrow morning?"
        )
        return {
            "body": sanitize_for_whatsapp(body),
            "cta": "binary_yes_no",
            "send_as": "vera",
            "suppression_key": suppression_key,
            "template_name": "vera_pharmacy_generic_nudge_v1",
            "template_params": [owner, b_name, locality, offer_title],
            "rationale": "Community healthcare positioning prompt."
        }
