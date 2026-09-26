#!/usr/bin/env python3
"""
scripts/live_smoke_test.py
===========================
End-to-end automated smoke test for the deployed Magicpin Vera AI challenge API.
Calls the live deployment directly (or local/specified URL) without requiring manual Swagger ID copying.

Usage:
    python scripts/live_smoke_test.py [BASE_URL]
    Example:
    python scripts/live_smoke_test.py https://magicpin-vera-bot-1zv0.onrender.com
"""

import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple, Optional

DEFAULT_BASE_URL = "https://magicpin-vera-bot-1zv0.onrender.com"

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def print_banner(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

def safe_str(val: Any) -> str:
    s = str(val if val is not None else "")
    return s.encode("ascii", errors="replace").decode("ascii")

def http_request(method: str, url: str, body: Optional[dict] = None, timeout: int = 25) -> Tuple[int, dict, float]:
    """Execute HTTP request, returns (status_code, response_json_or_text, elapsed_ms)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000
            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = {"raw": content}
            return resp.status, parsed, elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content, "error": str(e)}
        return e.code, parsed, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return 0, {"error": str(e)}, elapsed_ms

class TestResult:
    def __init__(self, name: str, passed: bool, status: int, latency_ms: float, details: str):
        self.name = name
        self.passed = passed
        self.status = status
        self.latency_ms = latency_ms
        self.details = details

def load_official_category_payload() -> dict:
    """Load full official dentists category payload to ensure complete schema compliance."""
    cat_file = Path("dataset/categories/dentists.json")
    if cat_file.exists():
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"slug": "dentists", "display_name": "Dentists & Oral Healthcare"}

def run_smoke_test(base_url: str) -> bool:
    base_url = base_url.rstrip("/")
    results: list[TestResult] = []

    print_banner(f"VERA LIVE API SMOKE TEST — {base_url}")
    print(f"Target deployment: {Colors.BOLD}{base_url}{Colors.RESET}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")

    # --------------------------------------------------------------------------
    # 1. GET /v1/healthz
    # --------------------------------------------------------------------------
    print(f"[*] Testing GET /v1/healthz ...")
    status, data, lat = http_request("GET", f"{base_url}/v1/healthz")
    passed = (status == 200 and data.get("status") == "ok" and "contexts_loaded" in data)
    details = f"status={data.get('status')}, uptime={data.get('uptime_seconds')}s, contexts={data.get('contexts_loaded')}"
    results.append(TestResult("GET /v1/healthz", passed, status, lat, details))
    print(f"    {'PASS' if passed else 'FAIL'} [{status}] ({lat:.0f}ms) — {details}")

    # --------------------------------------------------------------------------
    # 2. GET /v1/metadata
    # --------------------------------------------------------------------------
    print(f"[*] Testing GET /v1/metadata ...")
    status, data, lat = http_request("GET", f"{base_url}/v1/metadata")
    passed = (status == 200 and data.get("team_name") and data.get("model") and data.get("approach"))
    details = f"team={data.get('team_name')}, model={data.get('model')}, ver={data.get('version')}"
    results.append(TestResult("GET /v1/metadata", passed, status, lat, details))
    print(f"    {'PASS' if passed else 'FAIL'} [{status}] ({lat:.0f}ms) — {details}")

    # --------------------------------------------------------------------------
    # 3. POST /v1/context (Full Context Setup: Category, Merchant, Customer, Trigger)
    # --------------------------------------------------------------------------
    print(f"[*] Testing POST /v1/context (versioned storage & rejection) ...")
    ts = int(time.time())
    fresh_ver = int(time.time() * 1000)
    cat_payload = load_official_category_payload()

    # 3A: Push Category
    push_cat = {
        "scope": "category",
        "context_id": "dentists",
        "version": fresh_ver,
        "payload": cat_payload
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/context", push_cat)
    passed_cat = (status == 200 and data.get("accepted") is True and "ack_id" in data)
    results.append(TestResult("POST /v1/context (category)", passed_cat, status, lat, f"accepted={data.get('accepted')}, ack={data.get('ack_id')}"))
    print(f"    {'PASS' if passed_cat else 'FAIL'} Category Push [{status}] ({lat:.0f}ms) — ack={data.get('ack_id')}")

    # 3B: Push Merchant
    push_merch = {
        "scope": "merchant",
        "context_id": "m_001_drmeera_dentist_delhi",
        "version": fresh_ver,
        "payload": {
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "category_slug": "dentists",
            "identity": {
                "name": "Dr. Meera Dental Clinic",
                "owner_first_name": "Meera",
                "locality": "Malviya Nagar"
            }
        }
    }
    status_m, data_m, lat_m = http_request("POST", f"{base_url}/v1/context", push_merch)
    passed_m = (status_m == 200 and data_m.get("accepted") is True)
    results.append(TestResult("POST /v1/context (merchant)", passed_m, status_m, lat_m, f"accepted={data_m.get('accepted')}, ack={data_m.get('ack_id')}"))
    print(f"    {'PASS' if passed_m else 'FAIL'} Merchant Push [{status_m}] ({lat_m:.0f}ms) — ack={data_m.get('ack_id')}")

    # 3C: Push Customer
    push_cust = {
        "scope": "customer",
        "context_id": "c_001_priya_for_m001",
        "version": fresh_ver,
        "payload": {
            "customer_id": "c_001_priya_for_m001",
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "identity": {"name": "Priya Sharma"},
            "relationship": {"visit_count": 3}
        }
    }
    status_c, data_c, lat_c = http_request("POST", f"{base_url}/v1/context", push_cust)
    passed_c = (status_c == 200 and data_c.get("accepted") is True)
    results.append(TestResult("POST /v1/context (customer)", passed_c, status_c, lat_c, f"accepted={data_c.get('accepted')}, ack={data_c.get('ack_id')}"))
    print(f"    {'PASS' if passed_c else 'FAIL'} Customer Push [{status_c}] ({lat_c:.0f}ms) — ack={data_c.get('ack_id')}")

    # 3D: Push Trigger with fresh, non-colliding execution identifier
    live_trg_id = f"trg_live_recall_{ts}"
    live_supp_key = f"recall_due:priya:live_{ts}"
    push_trg = {
        "scope": "trigger",
        "context_id": live_trg_id,
        "version": fresh_ver,
        "payload": {
            "id": live_trg_id,
            "scope": "customer",
            "kind": "recall_due",
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "customer_id": "c_001_priya_for_m001",
            "payload": {
                "service_due": "6_month_cleaning",
                "last_service_date": "2026-05-12",
                "due_date": "2026-11-12"
            },
            "urgency": 3,
            "suppression_key": live_supp_key
        }
    }
    status_t, data_t, lat_t = http_request("POST", f"{base_url}/v1/context", push_trg)
    passed_t = (status_t == 200 and data_t.get("accepted") is True)
    results.append(TestResult("POST /v1/context (trigger)", passed_t, status_t, lat_t, f"accepted={data_t.get('accepted')}, ack={data_t.get('ack_id')}"))
    print(f"    {'PASS' if passed_t else 'FAIL'} Trigger Push [{status_t}] ({lat_t:.0f}ms) — ack={data_t.get('ack_id')}")

    # 3E: Stale version rejection test
    stale_body = {
        "scope": "category",
        "context_id": "dentists",
        "version": fresh_ver - 1,
        "payload": {"slug": "dentists"}
    }
    status_stale, data_stale, lat_stale = http_request("POST", f"{base_url}/v1/context", stale_body)
    passed_stale = (status_stale == 409 and data_stale.get("accepted") is False and data_stale.get("reason") == "stale_version")
    results.append(TestResult("POST /v1/context (stale rejection)", passed_stale, status_stale, lat_stale, f"status={status_stale}, reason={data_stale.get('reason')}"))
    print(f"    {'PASS' if passed_stale else 'FAIL'} Stale Rejection [{status_stale}] ({lat_stale:.0f}ms) — reason={data_stale.get('reason')}")

    # --------------------------------------------------------------------------
    # 4. POST /v1/tick (Proactive triggers & Automatic ID capture)
    # --------------------------------------------------------------------------
    print(f"\n[*] Testing POST /v1/tick (proactive trigger dispatch) ...")
    now_iso = datetime.now(timezone.utc).isoformat()
    tick_body = {
        "now": now_iso,
        "available_triggers": [live_trg_id]
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/tick", tick_body)
    actions = data.get("actions", [])
    passed_tick = (status == 200 and isinstance(actions, list) and len(actions) >= 1)
    results.append(TestResult("POST /v1/tick", passed_tick, status, lat, f"actions_count={len(actions)}"))
    print(f"    {'PASS' if passed_tick else 'FAIL'} [{status}] ({lat:.0f}ms) — Generated {len(actions)} action(s)")

    # Capture IDs directly from returned action
    if actions:
        action = actions[0]
        conv_cust = action["conversation_id"]
        mid_cust = action["merchant_id"]
        cid_cust = action["customer_id"]
        print(f"    Captured Action IDs: conv={conv_cust}, merchant={mid_cust}, customer={cid_cust}")
        safe_body_snip = safe_str(action.get('body', ''))[:80]
        print(f"    Action Body: \"{safe_body_snip}...\"")
    else:
        conv_cust = f"conv_m_001_{live_trg_id}"
        mid_cust = "m_001_drmeera_dentist_delhi"
        cid_cust = "c_001_priya_for_m001"

    mid_merch = mid_cust
    conv_merch = f"conv_merch_smoke_{ts}"

    # --------------------------------------------------------------------------
    # 5. POST /v1/reply — Customer Flow (Interest, Slot Selection, Cancellation)
    # --------------------------------------------------------------------------
    print(f"\n[*] Testing POST /v1/reply — Customer Flow ...")

    # 5A: Customer expresses interest ("Yes, please share the details.")
    c_turn1_body = {
        "conversation_id": conv_cust,
        "merchant_id": mid_cust,
        "customer_id": cid_cust,
        "from_role": "customer",
        "message": "Yes, please share the details.",
        "turn_number": 2
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", c_turn1_body)
    reply_body = (data.get("body") or "").lower()
    
    # Assertions:
    # 1. Action must be "send"
    # 2. CTA must be slot/package selection
    # 3. Must be relevant to Dr. Meera / dental / checkup / cleaning
    # 4. Must NOT falsely claim an appointment is already booked/scheduled
    no_premature_claim = ("is confirmed" not in reply_body and "i have scheduled" not in reply_body)
    relevant = any(k in reply_body for k in ["meera", "dental", "clinic", "checkup", "cleaning", "₹", "package", "details"])
    passed_c1 = (status == 200 and data.get("action") == "send" and data.get("cta") == "multi_choice_slot" and no_premature_claim and relevant)
    
    details_c1 = f"action={data.get('action')}, cta={data.get('cta')}, relevant={relevant}, no_premature_claim={no_premature_claim}"
    results.append(TestResult("POST /v1/reply (Customer: Interest)", passed_c1, status, lat, details_c1))
    print(f"    {'PASS' if passed_c1 else 'FAIL'} Customer Interest [{status}] ({lat:.0f}ms) — {details_c1}")
    print(f"         Snippet: \"{safe_str(data.get('body', ''))[:85]}...\"")

    # 5B: Customer slot selection ("1, Wednesday 6pm works for me")
    c_turn2_body = {
        "conversation_id": conv_cust,
        "merchant_id": mid_cust,
        "customer_id": cid_cust,
        "from_role": "customer",
        "message": "1, Wednesday 6pm works for me",
        "turn_number": 3
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", c_turn2_body)
    reply_body2 = (data.get("body") or "").lower()
    confirmed = "confirmed" in reply_body2 and "cancel" in reply_body2
    passed_c2 = (status == 200 and data.get("action") == "send" and data.get("cta") == "binary_confirm_cancel" and confirmed)
    details_c2 = f"action={data.get('action')}, cta={data.get('cta')}, booking_confirmed={confirmed}"
    results.append(TestResult("POST /v1/reply (Customer: Slot Confirm)", passed_c2, status, lat, details_c2))
    print(f"    {'PASS' if passed_c2 else 'FAIL'} Customer Slot Confirm [{status}] ({lat:.0f}ms) — {details_c2}")
    print(f"         Snippet: \"{safe_str(data.get('body', ''))[:85]}...\"")

    # 5C: Customer decline / cancel ("Cancel my booking for now, thank you.")
    c_turn3_body = {
        "conversation_id": f"conv_cust_cancel_{ts}",
        "merchant_id": mid_cust,
        "customer_id": cid_cust,
        "from_role": "customer",
        "message": "Please cancel my appointment for now, thank you.",
        "turn_number": 2
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", c_turn3_body)
    passed_c3 = (status == 200 and data.get("action") == "end")
    details_c3 = f"action={data.get('action')}, closed_gracefully=True"
    results.append(TestResult("POST /v1/reply (Customer: Cancel/Decline)", passed_c3, status, lat, details_c3))
    print(f"    {'PASS' if passed_c3 else 'FAIL'} Customer Cancel [{status}] ({lat:.0f}ms) — {details_c3}")

    # --------------------------------------------------------------------------
    # 6. POST /v1/reply — Merchant Flow (Commitment, Modification, Approval, Reject)
    # --------------------------------------------------------------------------
    print(f"\n[*] Testing POST /v1/reply — Merchant Flow ...")

    # 6A: Merchant Commitment / Transition ("Ok lets do it. Whats next?")
    m_turn1_body = {
        "conversation_id": conv_merch,
        "merchant_id": mid_merch,
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "turn_number": 2
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", m_turn1_body)
    m_body1 = (data.get("body") or "").lower()

    # Judge criteria: Actioning words present, qualifying words absent
    actioning_words = ["done", "draft", "here", "confirm", "proceed", "next", "sending"]
    qualifying_words = ["would you", "do you", "can you tell", "what if", "how about"]
    has_actioning = any(w in m_body1 for w in actioning_words)
    has_qualifying = any(w in m_body1 for w in qualifying_words)
    no_premature_publish = ("scheduled for tomorrow morning at 10:00 am" not in m_body1)

    passed_m1 = (status == 200 and data.get("action") == "send" and has_actioning and not has_qualifying and no_premature_publish)
    details_m1 = f"action={data.get('action')}, actioning={has_actioning}, qualifying={has_qualifying}, no_premature_claim={no_premature_publish}"
    results.append(TestResult("POST /v1/reply (Merchant: Commitment)", passed_m1, status, lat, details_m1))
    print(f"    {'PASS' if passed_m1 else 'FAIL'} Merchant Commitment [{status}] ({lat:.0f}ms) — {details_m1}")
    print(f"         Snippet: \"{safe_str(data.get('body', ''))[:85]}...\"")

    # 6B: Merchant Modification ("Can we change discount to 15% instead?")
    m_mod_conv = f"conv_m_mod_{ts}"
    m_turn2_body = {
        "conversation_id": m_mod_conv,
        "merchant_id": mid_merch,
        "from_role": "merchant",
        "message": "Can we change discount to 15% instead?",
        "turn_number": 2
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", m_turn2_body)
    m_body2 = (data.get("body") or "").lower()
    reflects_discount = "15%" in m_body2
    requests_confirm = "confirm" in m_body2
    no_premature_claim2 = ("scheduled for tomorrow morning at 10:00 am" not in m_body2)

    passed_m2 = (status == 200 and data.get("action") == "send" and reflects_discount and requests_confirm and no_premature_claim2)
    details_m2 = f"action={data.get('action')}, reflects_15%={reflects_discount}, requests_confirm={requests_confirm}"
    results.append(TestResult("POST /v1/reply (Merchant: Modification)", passed_m2, status, lat, details_m2))
    print(f"    {'PASS' if passed_m2 else 'FAIL'} Merchant Modification [{status}] ({lat:.0f}ms) — {details_m2}")
    print(f"         Snippet: \"{safe_str(data.get('body', ''))[:85]}...\"")

    # 6C: Merchant Final Confirmation ("Looks good, publish it")
    m_turn3_body = {
        "conversation_id": m_mod_conv,
        "merchant_id": mid_merch,
        "from_role": "merchant",
        "message": "Looks good, publish it",
        "turn_number": 3
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", m_turn3_body)
    m_body3 = (data.get("body") or "").lower()
    scheduled = "scheduled" in m_body3 and "10:00 am" in m_body3
    passed_m3 = (status == 200 and data.get("action") == "send" and data.get("cta") == "none" and scheduled)
    details_m3 = f"action={data.get('action')}, cta={data.get('cta')}, scheduled={scheduled}"
    results.append(TestResult("POST /v1/reply (Merchant: Final Confirm)", passed_m3, status, lat, details_m3))
    print(f"    {'PASS' if passed_m3 else 'FAIL'} Merchant Final Confirm [{status}] ({lat:.0f}ms) — {details_m3}")
    print(f"         Snippet: \"{safe_str(data.get('body', ''))[:85]}...\"")

    # 6D: Merchant Rejection ("Don't post, cancel this draft")
    m_turn4_body = {
        "conversation_id": f"conv_m_rej_{ts}",
        "merchant_id": mid_merch,
        "from_role": "merchant",
        "message": "Don't post, cancel this draft",
        "turn_number": 2
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/reply", m_turn4_body)
    passed_m4 = (status == 200 and data.get("action") == "end")
    details_m4 = f"action={data.get('action')}, draft_cancelled=True"
    results.append(TestResult("POST /v1/reply (Merchant: Rejection)", passed_m4, status, lat, details_m4))
    print(f"    {'PASS' if passed_m4 else 'FAIL'} Merchant Rejection [{status}] ({lat:.0f}ms) — {details_m4}")

    # --------------------------------------------------------------------------
    # SUMMARY REPORT
    # --------------------------------------------------------------------------
    print_banner("VERA LIVE API VERIFICATION REPORT")
    print(f"{'TEST CASE':<40} | {'STATUS':<6} | {'CODE':<5} | {'LATENCY':<8} | {'DETAILS'}")
    print(f"{'-'*40}-+-{'-'*6}-+-{'-'*5}-+-{'-'*8}-+-{'-'*35}")

    all_passed = True
    for r in results:
        status_str = f"{Colors.GREEN}PASS{Colors.RESET}" if r.passed else f"{Colors.RED}FAIL{Colors.RESET}"
        if not r.passed:
            all_passed = False
        print(f"{r.name:<40} | {status_str:<15} | {r.status:<5} | {r.latency_ms:6.0f}ms | {r.details}")

    print(f"\n{Colors.BOLD}TOTAL TESTS: {len(results)} | PASSED: {sum(1 for r in results if r.passed)} | FAILED: {sum(1 for r in results if not r.passed)}{Colors.RESET}")
    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}>>> ALL {len(results)}/{len(results)} LIVE API SMOKE TESTS PASSED PERFECTLY ON RENDER! <<<{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}>>> SOME SMOKE TESTS FAILED. INSPECT LOGS ABOVE. <<<{Colors.RESET}\n")

    return all_passed

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    success = run_smoke_test(target)
    sys.exit(0 if success else 1)
