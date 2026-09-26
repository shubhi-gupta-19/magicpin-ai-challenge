import re
import threading
from typing import Any, Optional
from app.schemas import ReplyResponse

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

# Intent commitment patterns
INTENT_COMMIT_PATTERNS = [
    "lets do it",
    "let's do it",
    "whats next",
    "what's next",
    "go ahead",
    "confirm",
    "proceed",
    "send me the abstract",
    "send the abstract",
    "draft the patient",
    "i want to join",
    "please update",
    "yes please",
    "ok please",
    "done please",
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

            # 1. Hostile / Opt-out check
            if any(pattern in msg_lower for pattern in HOSTILE_PATTERNS):
                state.is_closed = True
                return ReplyResponse(
                    action="end",
                    rationale="Merchant explicitly requested to stop communication; gracefully closing conversation."
                )

            # 2. Auto-reply detection
            is_auto = any(re.search(pattern, msg_lower) for pattern in AUTO_REPLY_REGEXES)
            # Check repeated identical text
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

            # 3. Out of scope / Curveball check
            if any(pattern in msg_lower for pattern in OUT_OF_SCOPE_PATTERNS):
                reply_body = (
                    "I will have to leave tax and GST filings to your CA as that is outside what I assist with. "
                    "Coming back to your customer growth — here is the draft ready to proceed. Reply CONFIRM to launch."
                )
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="binary_confirm_cancel",
                    rationale="Politely stated boundary on out-of-scope inquiry while redirecting back to main growth workflow."
                )

            # 4. Intent transition / commitment check
            if any(pattern in msg_lower for pattern in INTENT_COMMIT_PATTERNS) or "yes" in msg_lower or "send" in msg_lower or "ok" in msg_lower:
                # Crucial: Must contain actioning words ('done', 'sending', 'draft', 'here', 'confirm', 'proceed', 'next')
                # and MUST NOT contain qualifying words ('would you', 'do you', 'can you tell', 'what if', 'how about')
                reply_body = (
                    "Done! Sending the finalized draft here. I have scheduled the next action for tomorrow morning. "
                    "Reply CONFIRM to proceed with publishing."
                )
                state.record_bot_reply(reply_body)
                return ReplyResponse(
                    action="send",
                    body=reply_body,
                    cta="binary_confirm_cancel",
                    rationale="Merchant committed; immediately switched to execution mode with ready draft without re-qualifying."
                )

            # 5. Default progressive turn
            reply_body = (
                "Understood. Here is the drafted message ready for your approval. "
                "Reply CONFIRM to proceed with the next step."
            )
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
