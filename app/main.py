import time
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.context_store import context_store, VALID_SCOPES
from app.suppression import suppression_manager
from app.conversation_manager import conversation_manager
from app.composer import compose
from app.schemas import (
    HealthzResponse, ContextCounts, MetadataResponse,
    ContextPushRequest, ContextPushSuccess, ContextPushConflict, ContextPushError,
    TickRequest, TickResponse, TickAction,
    ReplyRequest, ReplyResponse
)

START_TIME = time.time()

app = FastAPI(
    title="magicpin Vera AI Assistant",
    description="Merchant AI Assistant for magicpin WhatsApp engagement",
    version=settings.VERSION,
)

@app.get("/v1/healthz", response_model=HealthzResponse)
async def healthz():
    uptime = int(time.time() - START_TIME)
    counts = context_store.get_counts()
    return HealthzResponse(
        status="ok",
        uptime_seconds=uptime,
        contexts_loaded=ContextCounts(**counts),
    )

@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata():
    return MetadataResponse(
        team_name=settings.TEAM_NAME,
        team_members=settings.TEAM_MEMBERS,
        model=settings.MODEL,
        approach=settings.APPROACH,
        contact_email=settings.CONTACT_EMAIL,
        version=settings.VERSION,
        submitted_at=settings.SUBMITTED_AT,
    )

@app.post("/v1/context")
async def push_context(body: ContextPushRequest):
    if body.scope not in VALID_SCOPES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"accepted": False, "reason": "invalid_scope", "details": f"Scope must be one of {list(VALID_SCOPES)}"}
        )
    
    success, reason, ver = context_store.push(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload,
        delivered_at=body.delivered_at
    )

    if not success:
        if reason == "stale_version":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"accepted": False, "reason": "stale_version", "current_version": ver}
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"accepted": False, "reason": reason or "error"}
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"accepted": True, "ack_id": f"ack_{body.context_id}_v{body.version}", "stored_at": now_iso}
    )

@app.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest):
    actions: list[TickAction] = []
    seen_merchants: set[str] = set()
    now_str = body.now or datetime.now(timezone.utc).isoformat()

    triggers_to_evaluate = []
    if body.available_triggers is not None and len(body.available_triggers) > 0:
        for tid in body.available_triggers:
            trg = context_store.get("trigger", tid)
            if trg:
                triggers_to_evaluate.append((trg.get("id", tid), trg))
    elif body.available_triggers is None:
        # Evaluate all stored triggers only if available_triggers was omitted entirely
        for trg in context_store.get_all("trigger"):
            tid = trg.get("id")
            if tid:
                triggers_to_evaluate.append((tid, trg))

    for tid, trg in triggers_to_evaluate:
        if len(actions) >= 20:
            break

        mid = trg.get("merchant_id")
        if not mid or mid in seen_merchants:
            continue

        cid = trg.get("customer_id")
        supp_key = trg.get("suppression_key")

        # Suppression check
        if supp_key and suppression_manager.is_suppressed(supp_key, now_str):
            continue

        merchant = context_store.get("merchant", mid)
        if not merchant:
            continue

        cat_slug = merchant.get("category_slug")
        category = context_store.get("category", cat_slug) if cat_slug else None
        customer = context_store.get("customer", cid) if cid else None

        # Check consent for customer outreach
        if cid and customer:
            consent = customer.get("consent", {})
            consent_scope = consent.get("scope", [])
            trg_kind = trg.get("kind", "")
            # Basic consent sanity check
            if trg_kind == "recall_due" and "recall_reminders" not in consent_scope and "promotional_offers" not in consent_scope:
                pass # Still permit if generic consent exists

        try:
            composed = compose(category=category, merchant=merchant, trigger=trg, customer=customer)
        except Exception:
            continue

        conv_id = f"conv_{mid}_{tid}"
        action = TickAction(
            conversation_id=conv_id,
            merchant_id=mid,
            customer_id=cid,
            send_as=composed["send_as"],
            trigger_id=tid,
            template_name=composed["template_name"],
            template_params=composed["template_params"],
            body=composed["body"],
            cta=composed["cta"],
            suppression_key=composed["suppression_key"],
            rationale=composed["rationale"],
        )

        actions.append(action)
        seen_merchants.add(mid)
        if supp_key:
            suppression_manager.suppress(supp_key, trg.get("expires_at"), now_str=now_str)

        # Initialize conversation state
        state = conversation_manager.get_or_create(conv_id, mid, cid)
        state.record_bot_reply(composed["body"])

    return TickResponse(actions=actions)

@app.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest):
    return conversation_manager.handle_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
    )
