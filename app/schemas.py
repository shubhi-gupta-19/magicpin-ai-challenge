from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# /v1/healthz
class ContextCounts(BaseModel):
    category: int = 0
    merchant: int = 0
    customer: int = 0
    trigger: int = 0

class HealthzResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int
    contexts_loaded: ContextCounts

# /v1/metadata
class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str

# /v1/context
class ContextPushRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None

class ContextPushSuccess(BaseModel):
    accepted: bool = True
    ack_id: str
    stored_at: str

class ContextPushConflict(BaseModel):
    accepted: bool = False
    reason: str = "stale_version"
    current_version: int

class ContextPushError(BaseModel):
    accepted: bool = False
    reason: str
    details: Optional[str] = None

# /v1/tick
class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)

class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str
    template_params: list[str]
    body: str
    cta: str
    suppression_key: str
    rationale: str

class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)

# /v1/reply
class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1

class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str
