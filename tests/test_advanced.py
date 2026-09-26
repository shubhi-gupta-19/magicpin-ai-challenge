import json
from fastapi.testclient import TestClient

def test_context_update_reflection(client: TestClient):
    # Category
    client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": {"slug": "dentists"}
    })
    
    # Merchant v1: views = 1000
    client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_update_01",
        "version": 1,
        "payload": {
            "merchant_id": "m_update_01",
            "category_slug": "dentists",
            "identity": {"name": "Apex Clinic", "owner_first_name": "Karthik"},
            "customer_aggregate": {"high_risk_adult_count": 50},
            "performance": {"views": 1000}
        }
    })
    
    # Trigger v1
    client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": "trg_update_01",
        "version": 1,
        "payload": {
            "id": "trg_update_01",
            "merchant_id": "m_update_01",
            "kind": "research_digest",
            "scope": "merchant",
            "suppression_key": "supp_test_1"
        }
    })

    # Tick 1
    t1 = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": ["trg_update_01"]
    }).json()
    assert len(t1["actions"]) == 1
    assert "50 high-risk adult patients" in t1["actions"][0]["body"]

    # Merchant v2 update: high_risk_adult_count = 95
    client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_update_01",
        "version": 2,
        "payload": {
            "merchant_id": "m_update_01",
            "category_slug": "dentists",
            "identity": {"name": "Apex Clinic", "owner_first_name": "Karthik"},
            "customer_aggregate": {"high_risk_adult_count": 95},
            "performance": {"views": 2500}
        }
    })

    # Trigger v2 with new suppression key
    client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": "trg_update_02",
        "version": 1,
        "payload": {
            "id": "trg_update_02",
            "merchant_id": "m_update_01",
            "kind": "research_digest",
            "scope": "merchant",
            "suppression_key": "supp_test_2"
        }
    })

    t2 = client.post("/v1/tick", json={
        "now": "2026-04-26T11:00:00Z",
        "available_triggers": ["trg_update_02"]
    }).json()
    assert len(t2["actions"]) == 1
    # Successfully reflects the new version's data!
    assert "95 high-risk adult patients" in t2["actions"][0]["body"]

def test_suppression_expiration(client: TestClient):
    client.post("/v1/context", json={
        "scope": "category",
        "context_id": "gyms",
        "version": 1,
        "payload": {"slug": "gyms"}
    })
    client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_gym_01",
        "version": 1,
        "payload": {
            "merchant_id": "m_gym_01",
            "category_slug": "gyms",
            "identity": {"name": "Fit Co", "owner_first_name": "Akash"}
        }
    })
    client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": "trg_expire_01",
        "version": 1,
        "payload": {
            "id": "trg_expire_01",
            "merchant_id": "m_gym_01",
            "kind": "perf_spike",
            "scope": "merchant",
            "suppression_key": "supp_exp_key",
            "expires_at": "2026-04-26T12:00:00Z"
        }
    })

    # Tick at 10:00: Trigger sent and suppressed until 12:00
    r1 = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": ["trg_expire_01"]
    }).json()
    assert len(r1["actions"]) == 1

    # Tick at 11:00: Still suppressed
    r2 = client.post("/v1/tick", json={
        "now": "2026-04-26T11:00:00Z",
        "available_triggers": ["trg_expire_01"]
    }).json()
    assert len(r2["actions"]) == 0

    # Tick at 12:01: Suppression has expired!
    r3 = client.post("/v1/tick", json={
        "now": "2026-04-26T12:01:00Z",
        "available_triggers": ["trg_expire_01"]
    }).json()
    assert len(r3["actions"]) == 1
