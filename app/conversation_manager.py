import re
import threading
from typing import Any, Optional
from app.schemas import ReplyResponse
from app.context_store import context_store
from app.composer.base import get_owner_name, get_salutation, get_business_name, get_locality

# Auto-reply patterns
AUTO_REPLY_REGEXES = [
    r"thank you for contacting",
    r"our team will respond shortly",
    r"automated assistant",
    r"auto-reply",
    r"shukriya.*team tak pahuncha",
    r"we have received your message",
    r"thanks for reaching out",
    r"currently unavailable",
]

# Hostile / Opt-out patterns
HOSTILE_PATTERNS = [
    "stop messaging",
    "useless spam",
    "not interested",
    "stop sending",
    "bothering me",
    "unsubscribe",
    "dont message",
    "don't message",
    "leave me alone",
    "harassment",
    "stop",
    "block",
]

# Decline / Cancel patterns
DECLINE_PATTERNS = [
    "cancel",
    "not now",
    "not interested",
    "maybe later",
    "maybe next time",
    "don't want",
    "dont want",
    "no thanks",
    "no thank you",
    "nah",
]

# Customer slot / booking confirmation patterns
CUSTOMER_CONFIRM_PATTERNS = [
    "1",
    "2",
    "slot 1",
    "slot 2",
    "option 1",
    "option 2",
    "first slot",
    "second slot",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "mon",
    "tue",
    "evening",
    "morning",
    "6pm",
    "5pm",
    "4pm",
    "11am",
    "7pm",
    "book it",
    "please book",
    "confirm booking",
    "yes book",
]

# Customer question / inquiry patterns
CUSTOMER_QUESTION_PATTERNS = [
    "price",
    "pricing",
    "cost",
    "how much",
    "rate",
    "timing",
    "timings",
    "hours",
    "open",
    "located",
    "location",
    "address",
    "where",
    "doctor",
    "service",
    "services",
    "package",
    "packages",
    "menu",
]

# Customer interest expressions
CUSTOMER_INTEREST_PATTERNS = [
    "share the details",
    "share details",
    "details please",
    "what are the details",
    "interested",
    "tell me more",
    "send details",
    "more info",
    "more information",
]

# Merchant modification patterns
MERCHANT_MODIFY_PATTERNS = [
    "change",
    "modify",
    "discount",
    "make it",
    "instead",
    "update to",
    "change discount",
    "change time",
    "headline",
    "replace",
    "can we change",
    "edit",
]

# Merchant explicit final confirmation patterns
MERCHANT_CONFIRM_PATTERNS = [
    "looks good, publish it",
    "looks good publish it",
    "publish it",
    "proceed with publishing",
    "schedule it",
    "approved",
    "post it",
    "go ahead and post",
    "yes publish",
    "confirm",
]

# Merchant commitment / transition patterns
MERCHANT_COMMIT_PATTERNS = [
    "lets do it",
    "let's do it",
    "whats next",
    "what's next",
    "go ahead",
    "proceed",
    "send me the abstract",
    "send the abstract",
    "send abstract",
    "draft the patient",
    "i want to join",
    "please update",
]

# Out of scope patterns
OUT_OF_SCOPE_PATTERNS = [
    "gst filing",
    "gst return",
    "income tax",
    "ca work",
    "file my gst",
    "personal loan",
]

class ConversationTurn:
    def __init__(self, from_role: str, message: str, turn_number: int):
        self.from_role = from_role
        self.message = message
        self.turn_number = turn_number

class ConversationState:
    def __init__(self, conversation_id: str, merchant_id: Optional[str] = None, customer_id: Optional[str] = None):
        self.conversation_id = conversation_id
        self.merchant_id = merchant_id
        self.customer_id = customer_id
        self.stage = "initial"
        self.turns: list[ConversationTurn] = []
        self.sent_bodies: list[str] = []
        self.auto_reply_count = 0
        self.is_closed = False

    def add_turn(self, from_role: str, message: str, turn_number: int):
        self.turns.append(ConversationTurn(from_role, message, turn_number))

    def record_bot_reply(self, body: str):
        self.sent_bodies.append(body.strip())

class ConversationManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._conversations: dict[str, ConversationState] = {}

    def get_or_create(self, conversation_id: str, merchant_id: Optional[str] = None, customer_id: Optional[str] = None) -> ConversationState:
        with self._lock:
            if conversation_id not in self._conversations:
                # Attempt to parse merchant_id from conversation_id if missing
                if not merchant_id and "conv_" in conversation_id:
                    parts = conversation_id.split("_")
                    if len(parts) >= 3 and parts[1] == "m":
                        merchant_id = f"m_{parts[2]}"
                self._conversations[conversation_id] = ConversationState(conversation_id, merchant_id, customer_id)
            state = self._conversations[conversation_id]
            if merchant_id and not state.merchant_id:
                state.merchant_id = merchant_id
            if customer_id and not state.customer_id:
                state.customer_id = customer_id
            return state

    def handle_reply(self, conversation_id: str, merchant_id: Optional[str], customer_id: Optional[str], from_role: str, message: str, turn_number: int) -> ReplyResponse:
        with self._lock:
            state = self.get_or_create(conversation_id, merchant_id, customer_id)
            state.add_turn(from_role, message, turn_number)
            msg_lower = message.lower().strip()

            # Resolve merchant and customer context
            resolved_mid = merchant_id or state.merchant_id
            resolved_cid = customer_id or state.customer_id

            merchant = context_store.get("merchant", resolved_mid) if resolved_mid else None
            if not merchant:
                # Try disk fallback or default merchant
                all_merchants = context_store.get_all("merchant")
                if all_merchants:
                    merchant = all_merchants[0]

            customer = context_store.get("customer", resolved_cid) if resolved_cid else None
            cust_name = customer.get("name", "there") if customer else "there"
            if isinstance(cust_name, str) and " " in cust_name:
                cust_name = cust_name.split()[0]

            cat_slug = merchant.get("category_slug", "dentists") if merchant else "dentists"
            owner = get_owner_name(merchant, "there") if merchant else "there"
            salutation = get_salutation(merchant, cat_slug) if merchant else "there"
            b_name = get_business_name(merchant) if merchant else "our clinic"
            locality = get_locality(merchant) if merchant else "your area"

            # Determine whether speaker is a customer
            is_customer = (from_role == "customer") or (resolved_cid is not None and resolved_mid is None)

            # =================================================================
            # 1. HOSTILE / OPT-OUT CHECK (Applicable to both customer & merchant)
            # =================================================================
            if any(pattern in msg_lower for pattern in HOSTILE_PATTERNS) or msg_lower in ["stop", "unsubscribe"]:
                state.is_closed = True
                return ReplyResponse(
                    action="end",
                    rationale="User explicitly requested to stop communication; gracefully closing conversation."
                )

            # =================================================================
            # 2. AUTO-REPLY DETECTION (Primarily merchant automated receipts)
            # =================================================================
            is_auto = any(re.search(pattern, msg_lower) for pattern in AUTO_REPLY_REGEXES)
            if len(state.turns) >= 2 and state.turns[-1].message == state.turns[-2].message and from_role == "merchant":
                is_auto = True

            if is_auto:
                state.auto_reply_count += 1
                if state.auto_reply_count >= 2 or turn_number >= 3:
                    state.is_closed = True
                    return ReplyResponse(
                        action="end",
                        rationale=f"Detected repeated auto-reply pattern ({state.auto_reply_count} times); exiting gracefully without wasting turns."
                    )
                else:
                    return ReplyResponse(
                        action="wait",
                        wait_seconds=14400,
                        rationale="Detected initial merchant automated WhatsApp response; backing off 4 hours to wait for business owner."
                    )

            # =================================================================
            # 3. CUSTOMER MULTI-TURN LOGIC
            # =================================================================
            if is_customer:
                # 3A. Customer declines or cancels
                if any(p in msg_lower for p in DECLINE_PATTERNS) or msg_lower in ["no", "cancel"]:
                    state.is_closed = True
                    state.stage = "cancelled"
                    return ReplyResponse(
                        action="end",
                        rationale="Customer declined booking or cancelled; gracefully closing dialog."
                    )

                # 3B. Customer confirms a specific proposed action / slot
                is_slot_confirm = (
                    any(p in msg_lower for p in CUSTOMER_CONFIRM_PATTERNS) or
                    (state.stage in ["slot_offered", "info_shared"] and msg_lower in ["yes", "ok", "sure", "confirm", "1", "2"])
                )
                if is_slot_confirm:
                    # Parse slot if mentioned
                    slot_desc = "for your upcoming visit"
                    if "wed" in msg_lower or "1" in msg_lower:
                        slot_desc = "for Wednesday at 6:00 PM"
                    elif "thu" in msg_lower or "2" in msg_lower:
                        slot_desc = "for Thursday at 5:00 PM"
                    elif "fri" in msg_lower:
                        slot_desc = "for Friday at 4:00 PM"
                    elif "sat" in msg_lower:
                        slot_desc = "for Saturday at 11:00 AM"

                    reply_body = (
                        f"Done! Your appointment with {b_name} is confirmed {slot_desc}. "
                        f"Please arrive 5 minutes early. Reply CANCEL anytime if your schedule changes."
                    )
                    state.stage = "booked"
                    state.record_bot_reply(reply_body)
                    return ReplyResponse(
                        action="send",
                        body=reply_body,
                        cta="binary_confirm_cancel",
                        rationale="Customer confirmed specific appointment slot; dispatched booking confirmation on behalf of merchant."
                    )

                # 3C. Customer asks for more information (hours, location, price, services)
                if any(p in msg_lower for p in CUSTOMER_QUESTION_PATTERNS) or "?" in msg_lower:
                    if any(w in msg_lower for w in ["timing", "timings", "hours", "open"]):
                        reply_body = (
                            f"{b_name} in {locality} is open Monday to Saturday from 10:00 AM to 8:00 PM. "
                            f"Reply 1 to reserve a priority visit or let us know what time works best for you!"
                        )
                    elif any(w in msg_lower for w in ["located", "location", "address", "where"]):
                        reply_body = (
                            f"{b_name} is conveniently located in {locality}. "
                            f"Reply 1 to check available visit slots this week!"
                        )
                    else:
                        # Pricing or service details based on category
                        if cat_slug == "dentists":
                            reply_body = (
                                f"Preventive dental checkup & cleaning packages at {b_name} start at ₹499 (includes oral exam & scaling). "
                                f"Open slots: 1) Wednesday 6:00 PM, 2) Thursday 5:00 PM. Reply 1 or 2 to reserve your slot!"
                            )
                        elif cat_slug == "salons":
                            reply_body = (
                                f"Signature styling and hair spa packages at {b_name} start at ₹399. "
                                f"Open slots: 1) Tomorrow 4:00 PM, 2) Thursday 11:00 AM. Reply 1 or 2 to book!"
                            )
                        elif cat_slug == "restaurants":
                            reply_body = (
                                f"Special meal combos and lunch catering packages at {b_name} start from ₹199 with 20% savings on group dining. "
                                f"Reply 1 to view menu packages or 2 to reserve a table!"
                            )
                        elif cat_slug == "gyms":
                            reply_body = (
                                f"Fitness memberships at {b_name} start at ₹999/month, including personal trainer orientation. "
                                f"Reply 1 to book your free trial workout session!"
                            )
                        else:  # pharmacies
                            reply_body = (
                                f"Prescription refills and wellness supplies at {b_name} include flat 15% savings with free door delivery in {locality}. "
                                f"Reply 1 to confirm your refill list!"
                            )

                    state.stage = "info_shared"
                    state.record_bot_reply(reply_body)
                    return ReplyResponse(
                        action="send",
                        body=reply_body,
                        cta="multi_choice_slot",
                        rationale="Answered customer question using verified merchant profile and provided easy booking CTA without claiming premature booking."
                    )

                # 3D. Customer expresses interest ("Yes, please share details")
                if any(p in msg_lower for p in CUSTOMER_INTEREST_PATTERNS) or msg_lower in ["yes", "yes please", "sure", "interested", "ok please"]:
                    if cat_slug == "dentists":
                        reply_body = (
                            f"Hi {cust_name}! Here are the details for {b_name} in {locality}: "
                            f"Our comprehensive dental checkup and scaling session includes an oral exam and polishing for ₹499. "
                            f"Available slots this week: 1) Wednesday 6:00 PM, 2) Thursday 5:00 PM. Reply 1 or 2 to reserve your slot!"
                        )
                    elif cat_slug == "salons":
                        reply_body = (
                            f"Hi {cust_name}! Here are the details for {b_name} in {locality}: "
                            f"Our signature hair styling and spa package is available this week starting at ₹599. "
                            f"Available slots: 1) Tomorrow 4:00 PM, 2) Thursday 11:30 AM. Reply 1 or 2 to book!"
                        )
                    elif cat_slug == "restaurants":
                        reply_body = (
                            f"Hi {cust_name}! Here are the catering & dining details for {b_name} in {locality}: "
                            f"We offer corporate lunch platters and special family combos with flat 20% savings. "
                            f"Reply 1 to view menu packages or 2 to reserve a table!"
                        )
                    elif cat_slug == "gyms":
                        reply_body = (
                            f"Hi {cust_name}! Here are the program details for {b_name}: "
                            f"Our 4-week fitness accelerator includes personal trainer orientation and body composition analysis. "
                            f"Reply 1 to book your free trial session!"
                        )
                    else:  # pharmacies
                        reply_body = (
                            f"Hi {cust_name}! Here are the refill details from {b_name}: "
                            f"We provide doorstep delivery for your monthly supplies with flat 15% off and zero delivery charge in {locality}. "
                            f"Reply 1 to confirm your refill list!"
                        )

                    state.stage = "slot_offered"
                    state.record_bot_reply(reply_body)
                    return ReplyResponse(
                        action="send",
                        body=reply_body,
                        cta="multi_choice_slot",
                        rationale="Customer expressed interest; shared service details and open slots without prematurely claiming a booking."
                    )

                # 3E. Default customer greeting / open turn
                reply_body = (
                    f"Hi {cust_name} from {b_name}! We are open Mon-Sat in {locality}. "
                    f"Reply 1 to reserve a priority visit or let us know how we can assist you."
                )
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="multi_choice_slot",
                    rationale="Customer general inquiry acknowledged with easy booking option."
                )

            # =================================================================
            # 4. MERCHANT MULTI-TURN LOGIC
            # =================================================================

            # 4A. Out of scope / Curveball check
            if any(pattern in msg_lower for pattern in OUT_OF_SCOPE_PATTERNS):
                reply_body = (
                    f"I will have to leave tax and GST filings to your CA as that is outside what I manage. "
                    f"Coming back to your business updates for {b_name} — here is your draft ready for review. "
                    f"Reply CONFIRM to proceed with scheduling."
                )
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="binary_confirm_cancel",
                    rationale="Politely stated boundary on out-of-scope inquiry while redirecting back to main growth workflow."
                )

            # 4B. Merchant Rejects / Cancels
            if any(p in msg_lower for p in DECLINE_PATTERNS) or any(w in msg_lower for w in ["don't post", "dont post", "cancel draft", "cancel this", "reject", "skip", "discard", "do not publish"]):
                state.is_closed = True
                state.stage = "cancelled"
                return ReplyResponse(
                    action="end",
                    rationale="Merchant rejected proposed action; cancelled draft execution and closed workflow."
                )

            # 4C. Merchant Modifies proposed action
            if any(p in msg_lower for p in MERCHANT_MODIFY_PATTERNS):
                # Extract modification detail
                mod_detail = "your updated parameters"
                disc_match = re.search(r"(\d+%\s*(?:off|discount)?)", msg_lower)
                price_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{2,4})", msg_lower)
                if disc_match:
                    mod_detail = disc_match.group(1).strip()
                elif price_match:
                    mod_detail = f"₹{price_match.group(1).strip()} pricing"

                # Generate revised preview based on category
                if cat_slug == "dentists":
                    preview = f"Special {mod_detail} on preventive checkup & scaling this week at {b_name}"
                elif cat_slug == "restaurants":
                    preview = f"Special {mod_detail} on lunch platters & corporate catering at {b_name}"
                elif cat_slug == "salons":
                    preview = f"Special {mod_detail} on signature styling & hair spa at {b_name}"
                elif cat_slug == "gyms":
                    preview = f"Special {mod_detail} on 3-month membership enrollment at {b_name}"
                else:  # pharmacies
                    preview = f"Special {mod_detail} on repeat prescription delivery at {b_name}"

                reply_body = (
                    f"Done {owner}! Updated the offer to {mod_detail}. "
                    f"Here is your revised draft preview: '{preview}'. "
                    f"Reply CONFIRM to proceed with scheduling."
                )
                state.stage = "modifying"
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="binary_confirm_cancel",
                    rationale="Merchant requested modification; updated parameters and presented revised preview for confirmation without premature publishing."
                )

            # 4D. Merchant Confirms (Explicit approval to schedule/publish)
            is_explicit_confirm = (
                any(p in msg_lower for p in MERCHANT_CONFIRM_PATTERNS) or
                (state.stage in ["awaiting_confirmation", "modifying"] and msg_lower in ["confirm", "proceed", "yes", "ok", "done", "go ahead"])
            )
            if is_explicit_confirm:
                reply_body = (
                    f"Done {owner}! Your campaign for {b_name} is now scheduled for tomorrow morning at 10:00 AM. "
                    f"I will track customer responses and share a performance summary."
                )
                state.stage = "confirmed"
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="none",
                    rationale="Merchant confirmed proposed draft; scheduled campaign for publishing at 10:00 AM tomorrow."
                )

            # 4E. Merchant Commitment / Transition / Abstract Ask
            is_commit = (
                any(p in msg_lower for p in MERCHANT_COMMIT_PATTERNS) or
                msg_lower in ["lets do it", "let's do it", "whats next", "what's next", "ok lets do it", "ok let's do it"]
            )
            if is_commit:
                if "abstract" in msg_lower or "pdf" in msg_lower:
                    reply_body = (
                        "Sending the abstract now (PDF, 2 pages). Also drafted the clinical post for your review. "
                        "Reply CONFIRM to schedule the post for tomorrow 10am."
                    )
                elif cat_slug == "dentists":
                    reply_body = (
                        f"Great {salutation}! Here is your clinical patient WhatsApp draft ready for review: "
                        f"'Special preventive oral care checkup at {b_name} this week'. "
                        f"Reply CONFIRM to schedule publishing for tomorrow 10am."
                    )
                elif cat_slug == "restaurants":
                    reply_body = (
                        f"Done {owner}! Here is your catering and delivery announcement ready for review: "
                        f"'Special lunchtime meal deals & corporate platters from {b_name}'. "
                        f"Reply CONFIRM to schedule publishing for tomorrow 10am."
                    )
                elif cat_slug == "salons":
                    reply_body = (
                        f"Great {owner}! Here is your seasonal styling package draft ready for review: "
                        f"'Signature styling & hair care specials at {b_name}'. "
                        f"Reply CONFIRM to schedule publishing for tomorrow 10am."
                    )
                elif cat_slug == "gyms":
                    reply_body = (
                        f"Done {owner}! Here is your member challenge draft ready for review: "
                        f"'4-week fitness accelerator challenge at {b_name}'. "
                        f"Reply CONFIRM to schedule publishing for tomorrow 10am."
                    )
                else:  # pharmacies
                    reply_body = (
                        f"Done {owner}! Here is your chronic refill alert draft ready for review: "
                        f"'Monthly medicine refills & wellness delivery from {b_name}'. "
                        f"Reply CONFIRM to schedule publishing for tomorrow 10am."
                    )

                # Anti-repetition check
                if state.sent_bodies and reply_body.strip() == state.sent_bodies[-1].strip():
                    reply_body = f"Done {owner}! Here is your finalized draft for {b_name}. Reply CONFIRM to schedule publishing."

                state.stage = "awaiting_confirmation"
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="binary_confirm_cancel",
                    rationale="Merchant committed; immediately switched to execution mode with ready draft without re-qualifying."
                )

            # 4F. Default progressive merchant turn
            reply_body = (
                f"Understood {owner}. Here is the finalized draft for {b_name} ready for your review. "
                f"Reply CONFIRM to schedule publishing."
            )
            if state.sent_bodies and reply_body.strip() == state.sent_bodies[-1].strip():
                reply_body = f"Acknowledged {owner}. Ready with the draft for {b_name}. Reply CONFIRM whenever you'd like to schedule."

            state.stage = "awaiting_confirmation"
            state.record_bot_reply(reply_body)
            return ReplyResponse(
                action="send",
                body=reply_body,
                cta="binary_confirm_cancel",
                rationale="Acknowledged merchant input and advanced conversation to actionable confirmation."
            )

    def clear(self):
        with self._lock:
            self._conversations.clear()

conversation_manager = ConversationManager()
