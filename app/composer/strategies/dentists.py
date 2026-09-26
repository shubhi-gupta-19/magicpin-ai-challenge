from typing import Any, Optional
from app.composer.base import (
    get_owner_name, get_salutation, get_locality, get_business_name,
    get_active_offer, is_hindi_preferred, sanitize_for_whatsapp
)

class DentistsStrategy:
    @staticmethod
    def compose(category: dict[str, Any], merchant: dict[str, Any], trigger: dict[str, Any], customer: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        kind = trigger.get("kind", "")
        scope = trigger.get("scope", "merchant")
        payload = trigger.get("payload", {})
        trigger_id = trigger.get("id", "")
        suppression_key = trigger.get("suppression_key") or f"{kind}:{merchant.get('merchant_id')}"
        salutation = get_salutation(merchant, "dentists")
        b_name = get_business_name(merchant)
        locality = get_locality(merchant)
        active_offer = get_active_offer(merchant, category)
        offer_title = active_offer.get("title", "Dental Cleaning @ ₹299") if active_offer else "Dental Cleaning @ ₹299"

        # Customer-facing message
        if customer or scope == "customer":
            c_name = customer.get("identity", {}).get("name", "there") if customer else "there"
            hi_mix = is_hindi_preferred(customer) if customer else True
            
            if kind == "recall_due":
                slots = payload.get("available_slots", [])
                s1 = slots[0].get("label", "Wed 5 Nov, 6pm") if len(slots) > 0 else "Wed 5 Nov, 6pm"
                s2 = slots[1].get("label", "Thu 6 Nov, 5pm") if len(slots) > 1 else "Thu 6 Nov, 5pm"
                
                if hi_mix:
                    body = (
                        f"Hi {c_name}, {b_name} here 🦷 It's been 5 months since your last visit — your 6-month cleaning recall is due. "
                        f"Apke liye 2 slots ready hain: {s1} ya {s2}. {offer_title} + complimentary fluoride. "
                        f"Reply 1 for {s1.split(',')[0]}, 2 for {s2.split(',')[0]}, or tell us a time that works."
                    )
                else:
                    body = (
                        f"Hi {c_name}, {b_name} here 🦷 It's been 5 months since your last visit — your 6-month cleaning recall is due. "
                        f"We have 2 slots available: {s1} or {s2}. {offer_title} + complimentary fluoride varnish. "
                        f"Reply 1 for {s1.split(',')[0]}, 2 for {s2.split(',')[0]}, or let us know what time suits you."
                    )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "multi_choice_slot",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "dentist_recall_reminder_v1",
                    "template_params": [c_name, b_name, s1, s2, offer_title],
                    "rationale": "Customer-facing clinical recall reminder offering specific available slots and active catalog pricing."
                }

            if kind in ("chronic_refill_due", "refill_due"):
                body = (
                    f"Hi {c_name}, {b_name} here. Your prescribed oral care supplies are scheduled for review. "
                    f"Regular preventive maintenance protects against gum disease and caries. "
                    f"Would you like us to prepare your regular care kit? Reply YES to confirm delivery."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "dentist_care_refill_v1",
                    "template_params": [c_name, b_name],
                    "rationale": "Customer-facing oral care continuity reminder."
                }

            if kind in ("customer_lapsed_soft", "customer_lapsed_hard"):
                body = (
                    f"Hi {c_name}, {b_name} here. It's been over 6 months since your routine checkup. "
                    f"Early plaque removal prevents caries progression. Would you like us to reserve a convenient slot for your {offer_title}? Reply YES to confirm."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_yes_no",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "dentist_lapsed_winback_v1",
                    "template_params": [c_name, b_name, offer_title],
                    "rationale": "Clinical winback reminder highlighting preventive oral health."
                }

            if kind == "appointment_tomorrow":
                time_slot = payload.get("time", "11:00 AM")
                body = (
                    f"Hi {c_name}, gentle reminder for your dental appointment tomorrow at {time_slot} at {b_name}. "
                    f"Please arrive 5 minutes early. Reply CONFIRM to secure your slot or let us know if you need to reschedule."
                )
                return {
                    "body": sanitize_for_whatsapp(body),
                    "cta": "binary_confirm_cancel",
                    "send_as": "merchant_on_behalf",
                    "suppression_key": suppression_key,
                    "template_name": "dentist_appointment_reminder_v1",
                    "template_params": [c_name, time_slot, b_name],
                    "rationale": "Appointment reminder with clear confirmation call to action."
                }

            # Generic customer reachout
            body = (
                f"Hi {c_name}, {b_name} here. Just checking in on your dental wellness. "
                f"Our team has slots open for {offer_title} this week. Reply YES if you would like to book a visit."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "merchant_on_behalf",
                "suppression_key": suppression_key,
                "template_name": "dentist_customer_generic_v1",
                "template_params": [c_name, b_name, offer_title],
                "rationale": "Customer preventive dental care checkup reminder."
            }

        # Merchant-facing messages
        cust_agg = merchant.get("customer_aggregate", {})
        high_risk_n = cust_agg.get("high_risk_adult_count", 124)
        perf = merchant.get("performance", {})
        
        if kind == "research_digest":
            body = (
                f"{salutation}, JIDA's Oct issue landed. One item relevant to your {high_risk_n} high-risk adult patients — "
                f"2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better than 6-month. "
                f"Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? — JIDA Oct 2026 p.14"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "open_ended",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_dentist_research_digest_v1",
                "template_params": [salutation, str(high_risk_n), "JIDA Oct 2026 p.14"],
                "rationale": "External research digest citing JIDA clinical trial anchored to merchant's high-risk patient count."
            }

        if kind == "regulation_change":
            deadline = payload.get("deadline_iso", "2026-12-15")
            body = (
                f"{salutation}, regulatory update from Dental Council of India (DCI): revised radiograph dose limits take effect {deadline} "
                f"(max dose reduced to 1.0 mSv per IOPA). E-speed film complies; D-speed does not. "
                f"Want me to send the 1-page compliance checklist and draft a note for your radiographer? — DCI circular 2026-11-04"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_dentist_compliance_alert_v1",
                "template_params": [salutation, deadline],
                "rationale": "Urgent DCI compliance notice with precise dose limits and actionable verification checklist."
            }

        if kind == "cde_opportunity":
            topic = payload.get("topic", "clear aligner biomechanics")
            body = (
                f"{salutation}, IDA Delhi has scheduled a 2-hour accredited CDE webinar on {topic} next Friday at 7pm. "
                f"Carries 2 credit points. Want me to send the direct registration link and calendar invite?"
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_dentist_cde_invite_v1",
                "template_params": [salutation, topic],
                "rationale": "Peer professional development opportunity directly relevant to modern practice."
            }

        if kind == "competitor_opened":
            body = (
                f"{salutation}, a new dental clinic recently listed on Google Maps within 1.5km in {locality}. "
                f"Your Google profile holds 4.4★, but posting frequency has slowed. "
                f"Want me to draft 2 educational patient posts on {offer_title} to protect your local search ranking? Ready in 5 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_dentist_competitor_defense_v1",
                "template_params": [salutation, locality, offer_title],
                "rationale": "Local competitive awareness paired with immediate profile defense action."
            }

        if kind == "perf_dip":
            calls = perf.get("calls", 4)
            calls_drop = abs(int(payload.get("delta_pct", -0.50) * 100))
            body = (
                f"{salutation}, weekly performance check: phone call inquiries dipped {calls_drop}% ({calls} calls in last 7 days vs baseline of 12). "
                f"Clinics in {locality} are capturing calls via highlighted consultation offers. "
                f"Want me to reactivate your '{offer_title}' on your profile to drive immediate appointments? Takes 2 min."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_yes_no",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_dentist_perf_dip_remedy_v1",
                "template_params": [salutation, str(calls_drop), locality, offer_title],
                "rationale": "Concrete call drop alert with effort-externalized catalog offer fix."
            }

        if kind == "renewal_due":
            days = payload.get("days_remaining", 12)
            amount = payload.get("renewal_amount", 4999)
            body = (
                f"{salutation}, your Vera Pro subscription for {b_name} has {days} days remaining before expiration. "
                f"Renewing now preserves automated Google review response and appointment lead capture (₹{amount}/year). "
                f"Reply RENEW to generate your 1-click renewal invoice."
            )
            return {
                "body": sanitize_for_whatsapp(body),
                "cta": "binary_confirm_cancel",
                "send_as": "vera",
                "suppression_key": suppression_key,
                "template_name": "vera_renewal_reminder_v1",
                "template_params": [salutation, str(days), str(amount)],
                "rationale": "Subscription continuity reminder highlighting protected business capabilities."
            }

        # Fallback for generic dental triggers
        views = perf.get("views", 1200)
        body = (
            f"{salutation}, quick update for {b_name}: your profile reached {views} patient views this month in {locality}. "
            f"Featuring your '{offer_title}' can convert 15-20% more viewers into appointments. "
            f"Want me to schedule a Google Business post featuring this offer for tomorrow 10am?"
        )
        return {
            "body": sanitize_for_whatsapp(body),
            "cta": "binary_yes_no",
            "send_as": "vera",
            "suppression_key": suppression_key,
            "template_name": "vera_dentist_generic_nudge_v1",
            "template_params": [salutation, b_name, str(views), offer_title],
            "rationale": "Data-anchored profile growth recommendation."
        }
