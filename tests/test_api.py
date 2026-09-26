import json
from pathlib import Path
from fastapi.testclient import TestClient

def test_healthz(client: TestClient):
    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert "contexts_loaded" in data
    assert data["contexts_loaded"]["category"] == 0

def test_metadata(client: TestClient):
    resp = client.get("/v1/metadata")
    assert resp.status_code == 200
    data = resp.json()
    assert "team_name" in data
    assert "model" in data
    assert "version" in data
    assert "submitted_at" in data

def test_context_push_and_versioning(client: TestClient):
    cat_payload = {"slug": "dentists", "voice": {"tone": "peer_clinical"}}
    
    # 1. Successful push version 1
    resp1 = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_payload
    })
    assert resp1.status_code == 200
    assert resp1.json()["accepted"] is True
    assert "ack_dentists_v1" in resp1.json()["ack_id"]

    # 2. Check healthz count incremented
    hz = client.get("/v1/healthz").json()
    assert hz["contexts_loaded"]["category"] == 1

    # 3. Duplicate version conflict (version 1 again) -> 409
    resp_conflict = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_payload
    })
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["accepted"] is False
    assert resp_conflict.json()["reason"] == "stale_version"
    assert resp_conflict.json()["current_version"] == 1

    # 4. Version bump to version 2 -> 200
    resp_v2 = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 2,
        "payload": {**cat_payload, "updated": True}
    })
    assert resp_v2.status_code == 200
    assert resp_v2.json()["accepted"] is True
    assert "ack_dentists_v2" in resp_v2.json()["ack_id"]

    # 5. Invalid scope -> 400
    resp_bad = client.post("/v1/context", json={
        "scope": "invalid_scope",
        "context_id": "dentists",
        "version": 1,
        "payload": {}
    })
    assert resp_bad.status_code == 400
    assert resp_bad.json()["accepted"] is False

def test_tick_empty(client: TestClient):
    resp = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": []
    })
    assert resp.status_code == 200
    assert resp.json()["actions"] == []

def test_tick_with_contexts(client: TestClient):
    # Setup Category
    client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": {"slug": "dentists"}
    })
    # Setup Merchant
    client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_001",
        "version": 1,
        "payload": {
            "merchant_id": "m_001",
            "category_slug": "dentists",
            "identity": {"name": "Dr. Meera Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar"}
        }
    })
    # Setup Trigger
    client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": "trg_001",
        "version": 1,
        "payload": {
            "id": "trg_001",
            "merchant_id": "m_001",
            "kind": "research_digest",
            "scope": "merchant",
            "suppression_key": "research:dentists:W17"
        }
    })

    # Call Tick
    resp = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": ["trg_001"]
    })
    assert resp.status_code == 200
    actions = resp.json()["actions"]
    assert len(actions) == 1
    act = actions[0]
    assert act["merchant_id"] == "m_001"
    assert act["trigger_id"] == "trg_001"
    assert act["send_as"] == "vera"
    assert "Dr. Meera" in act["body"]
    assert act["cta"] is not None
    assert "research:dentists:W17" in act["suppression_key"]

    # Second Tick should suppress duplicate action
    resp2 = client.post("/v1/tick", json={
        "now": "2026-04-26T10:05:00Z",
        "available_triggers": ["trg_001"]
    })
    assert resp2.status_code == 200
    assert len(resp2.json()["actions"]) == 0

def test_tick_20_action_limit(client: TestClient):
    client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": {"slug": "dentists"}
    })
    
    triggers = []
    # Create 25 merchants and triggers
    for i in range(25):
        mid = f"m_{i:03d}"
        tid = f"trg_{i:03d}"
        client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": mid,
            "version": 1,
            "payload": {
                "merchant_id": mid,
                "category_slug": "dentists",
                "identity": {"name": f"Clinic {i}", "owner_first_name": f"Doctor{i}"}
            }
        })
        client.post("/v1/context", json={
            "scope": "trigger",
            "context_id": tid,
            "version": 1,
            "payload": {
                "id": tid,
                "merchant_id": mid,
                "kind": "research_digest",
                "scope": "merchant"
            }
        })
        triggers.append(tid)

    resp = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": triggers
    })
    assert resp.status_code == 200
    # Must enforce cap of 20
    assert len(resp.json()["actions"]) == 20

def test_reply_auto_reply_backoff_and_exit(client: TestClient):
    conv_id = "conv_test_autoreply"
    auto_msg = "Thank you for contacting us! Our team will respond shortly."

    # Turn 1: Bot should wait or acknowledge
    resp1 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": auto_msg,
        "turn_number": 1
    })
    assert resp1.status_code == 200
    assert resp1.json()["action"] in ("wait", "send")

    # Turn 2: Repeated auto-reply -> should end or wait
    resp2 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": auto_msg,
        "turn_number": 2
    })
    assert resp2.status_code == 200
    assert resp2.json()["action"] in ("end", "wait")

    # Turn 3: 3rd time -> MUST end gracefully
    resp3 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": auto_msg,
        "turn_number": 3
    })
    assert resp3.status_code == 200
    assert resp3.json()["action"] == "end"

def test_reply_intent_transition(client: TestClient):
    conv_id = "conv_test_intent"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    
    # Must contain actioning words
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    assert any(w in body_lower for w in actioning)

    # Must NOT contain qualifying words
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    assert not any(w in body_lower for w in qualifying)

def test_reply_hostile_opt_out(client: TestClient):
    conv_id = "conv_test_hostile"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Stop messaging me. This is useless spam.",
        "turn_number": 2
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "end"

def test_reply_out_of_scope_redirect(client: TestClient):
    conv_id = "conv_test_gst"
    resp = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Btw can you file my GST return?",
        "turn_number": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    assert "ca" in data["body"].lower() or "gst" in data["body"].lower()
