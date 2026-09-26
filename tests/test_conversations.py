import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.context_store import context_store
from app.conversation_manager import conversation_manager
from app.suppression import suppression_manager

@pytest.fixture
def client():
    # Clear state between tests
    suppression_manager.clear()
    conversation_manager.clear()
    return TestClient(app)

# ==============================================================================
# 1. LIVE-STYLE /v1/tick RESOLUTION TESTS
# ==============================================================================

def test_tick_with_live_style_trigger_aliases(client: TestClient):
    """
    Test that calling /v1/tick with high-level trigger aliases
    (['appointment_reminder', 'post_visit_followup', 'winback'])
    correctly resolves triggers and merchants from disk and produces actions.
    """
    resp = client.post("/v1/tick", json={
        "now": "2026-09-27T10:00:00Z",
        "available_triggers": ["appointment_reminder", "post_visit_followup", "winback"]
    })
    assert resp.status_code == 200
    data = resp.json()
    actions = data.get("actions", [])
    assert len(actions) == 3, f"Expected 3 actions, got {len(actions)}"

    # Check merchant deduplication and distinct merchants
    merchant_ids = [a["merchant_id"] for a in actions]
    assert len(set(merchant_ids)) == 3, "Each action must be for a distinct merchant"

    for action in actions:
        assert action["body"], "Action body must not be empty"
        assert action["cta"], "Action CTA must not be empty"
        assert action["send_as"] in ("vera", "merchant_on_behalf")
        assert action["suppression_key"], "Suppression key must be set"

    # Subsequent tick with same triggers and time should be suppressed
    resp2 = client.post("/v1/tick", json={
        "now": "2026-09-27T10:01:00Z",
        "available_triggers": ["appointment_reminder", "post_visit_followup", "winback"]
    })
    assert resp2.status_code == 200
    assert len(resp2.json().get("actions", [])) == 0, "Duplicate triggers should be suppressed"

def test_tick_with_explicit_empty_triggers(client: TestClient):
    """Calling /v1/tick with available_triggers=[] must return actions: []"""
    resp = client.post("/v1/tick", json={
        "now": "2026-09-27T10:00:00Z",
        "available_triggers": []
    })
    assert resp.status_code == 200
    assert resp.json().get("actions") == []

# ==============================================================================
# 2. CUSTOMER MULTI-TURN CONVERSATION TESTS
# ==============================================================================

def test_customer_expresses_interest_does_not_prematurely_book(client: TestClient):
    """
    Customer expresses interest: "Yes, please share the details."
    Must share details, pricing, or slot options.
    Must NOT claim that an appointment has been booked or scheduled.
    """
    conv_id = "conv_cust_interest_101"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": "c_001_priya_for_m001",
        "from_role": "customer",
        "message": "Yes, please share the details.",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body = data["body"]

    # Must provide service/package details
    assert "₹" in body or "package" in body.lower() or "slot" in body.lower() or "details" in body.lower()
    assert data["cta"] == "multi_choice_slot"

    # Must NOT claim that booking was completed or scheduled
    body_lower = body.lower()
    assert "is confirmed" not in body_lower
    assert "i have scheduled" not in body_lower

def test_customer_confirms_specific_slot(client: TestClient):
    """
    Customer confirms a specific slot: "1" or "Wed 6pm"
    Implementation can now confirm the appointment on behalf of merchant.
    """
    conv_id = "conv_cust_confirm_102"
    # Turn 2: Customer confirms slot
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": "c_001_priya_for_m001",
        "from_role": "customer",
        "message": "1, Wednesday 6pm works for me",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    assert "confirmed" in body_lower
    assert "cancel" in body_lower  # Provides cancel instructions
    assert data["cta"] == "binary_confirm_cancel"

def test_customer_declines_or_cancels(client: TestClient):
    """
    Customer declines or cancels: "No, cancel" or "not interested".
    Must close conversation gracefully without repeated outreach.
    """
    conv_id = "conv_cust_decline_103"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": "c_001_priya_for_m001",
        "from_role": "customer",
        "message": "No thanks, cancel this for now.",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "end"

def test_customer_asks_for_information(client: TestClient):
    """
    Customer asks for information: "What are your clinic timings?"
    Must answer operational details from merchant profile and offer next step CTA.
    """
    conv_id = "conv_cust_info_104"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": "c_001_priya_for_m001",
        "from_role": "customer",
        "message": "What are your clinic timings and where are you located?",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    assert "open" in body_lower or "mon" in body_lower or "10:00" in body_lower or "malviya" in body_lower
    # Must NOT claim booking completed
    assert "is confirmed" not in body_lower
    assert "i have scheduled" not in body_lower

# ==============================================================================
# 3. MERCHANT MULTI-TURN CONVERSATION TESTS
# ==============================================================================

def test_merchant_commitment_presents_draft_without_premature_claim(client: TestClient):
    """
    Merchant says "Ok lets do it. Whats next?"
    Must switch to action mode, present ready draft, invite CONFIRM.
    Must NOT prematurely claim the post is already published or scheduled.
    """
    conv_id = "conv_merch_commit_201"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()

    # Actioning words required by judge simulator
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    assert any(w in body_lower for w in actioning)

    # Qualifying words forbidden
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    assert not any(w in body_lower for w in qualifying)

    # Must invite CONFIRM without claiming it's already scheduled
    assert "confirm" in body_lower
    assert data["cta"] == "binary_confirm_cancel"

def test_merchant_modifies_proposed_action(client: TestClient):
    """
    Merchant modifies: "Change discount to 15%"
    Must acknowledge 15% discount, present revised preview, ask CONFIRM to schedule.
    Must NOT claim publishing has already occurred.
    """
    conv_id = "conv_merch_modify_202"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "from_role": "merchant",
        "message": "Can we change discount to 15% instead?",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    assert "15%" in body_lower
    assert "draft" in body_lower or "preview" in body_lower
    assert "confirm" in body_lower
    assert "scheduled for tomorrow morning at 10:00 am" not in body_lower
    assert data["cta"] == "binary_confirm_cancel"

def test_merchant_confirms_action(client: TestClient):
    """
    Merchant confirms: "Looks good, publish it"
    Now and only now claim campaign is scheduled for tomorrow 10am.
    """
    conv_id = "conv_merch_confirm_203"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "from_role": "merchant",
        "message": "Looks good, publish it",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    assert "scheduled" in body_lower
    assert "10:00 am" in body_lower
    assert data["cta"] == "none"

def test_merchant_rejects_action(client: TestClient):
    """
    Merchant rejects: "Don't post, cancel this draft"
    Must cancel execution and gracefully end.
    """
    conv_id = "conv_merch_reject_204"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "from_role": "merchant",
        "message": "Don't post, cancel this draft",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "end"
