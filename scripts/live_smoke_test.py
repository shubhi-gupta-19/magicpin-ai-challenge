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
    # 3. POST /v1/context (Fresh Push & Stale Version Rejection)
    # --------------------------------------------------------------------------
    print(f"[*] Testing POST /v1/context (versioned storage & rejection) ...")
    fresh_ver = int(time.time()) % 100000 + 20000
    cat_payload = load_official_category_payload()
    push_body = {
        "scope": "category",
        "context_id": "dentists",
        "version": fresh_ver,
        "payload": cat_payload
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/context", push_body)
    passed_push = (status == 200 and data.get("accepted") is True and "ack_id" in data)
    results.append(TestResult("POST /v1/context (fresh version)", passed_push, status, lat, f"accepted={data.get('accepted')}, ack={data.get('ack_id')}"))
    print(f"    {'PASS' if passed_push else 'FAIL'} Fresh Push [{status}] ({lat:.0f}ms) — ack={data.get('ack_id')}")

    # Stale version rejection test
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
    print(f"[*] Testing POST /v1/tick (proactive trigger dispatch) ...")
    # Provide diverse canonical candidate triggers across distinct merchants
    unique_now = f"2026-11-{int(time.time()) % 20 + 10:02d}T10:00:00Z"
    candidate_triggers = [
        "trg_077_appointment_tomorrow_m_020_renu_salon_luc",
        "trg_004_perf_dip_bharat",
        "trg_019_chronic_refill_grandfather",
        "trg_078_appointment_tomorrow_m_006_southindiancaf",
        "trg_008_perf_dip_pizzajunction",
        "trg_015_winback_rashmi"
    ]
    tick_body = {
        "now": unique_now,
        "available_triggers": candidate_triggers
    }
    status, data, lat = http_request("POST", f"{base_url}/v1/tick", tick_body)
    actions = data.get("actions", [])
    passed_tick = (status == 200 and isinstance(actions, list) and len(actions) >= 1)
    results.append(TestResult("POST /v1/tick", passed_tick, status, lat, f"actions_count={len(actions)}"))
    print(f"    {'PASS' if passed_tick else 'FAIL'} [{status}] ({lat:.0f}ms) — Generated {len(actions)} action(s)")

    # Automatically extract IDs from tick output without guessing
    cust_action = next((a for a in actions if a.get("customer_id")), None)
    merch_action = next((a for a in actions if not a.get("customer_id")), None)

    # Fallback to defaults only if specific role was filtered
    conv_cust = cust_action["conversation_id"] if cust_action else "conv_m_020_renu_salon_lucknow_live_smoke"
    mid_cust = cust_action["merchant_id"] if cust_action else "m_020_renu_salon_lucknow"
    cid_cust = cust_action["customer_id"] if cust_action else "c_080_riya_for_m_020_renu_salon_lucknow"

    conv_merch = merch_action["conversation_id"] if merch_action else f"conv_m_002_live_smoke_{int(time.time())}"
    mid_merch = merch_action["merchant_id"] if merch_action else "m_002_bharat_dentist_mumbai"

    print(f"    Captured Customer IDs: conv={conv_cust}, merchant={mid_cust}, customer={cid_cust}")
    print(f"    Captured Merchant IDs: conv={conv_merch}, merchant={mid_merch}")

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
    # 3. Must be relevant to merchant/category (not generic fallback)
    # 4. Must NOT falsely claim an appointment is already booked/scheduled
    no_premature_claim = ("is confirmed" not in reply_body and "i have scheduled" not in reply_body)
    relevant = any(k in reply_body for k in ["renu", "salon", "styling", "dental", "clinic", "checkup", "cleaning", "pharmacy", "refill", "₹", "package", "details"])
    passed_c1 = (status == 200 and data.get("action") == "send" and data.get("cta") == "multi_choice_slot" and no_premature_claim and relevant)
    
    details_c1 = f"action={data.get('action')}, cta={data.get('cta')}, relevant={relevant}, no_premature_claim={no_premature_claim}"
    results.append(TestResult("POST /v1/reply (Customer: Interest)", passed_c1, status, lat, details_c1))
    print(f"    {'PASS' if passed_c1 else 'FAIL'} Customer Interest [{status}] ({lat:.0f}ms) — {details_c1}")
    print(f"         Snippet: \"{data.get('body', '')[:85]}...\"")

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
    print(f"         Snippet: \"{data.get('body', '')[:85]}...\"")

    # 5C: Customer decline / cancel ("Cancel my booking for now, thank you.")
    c_turn3_body = {
        "conversation_id": f"conv_cust_cancel_{int(time.time())}",
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
    print(f"         Snippet: \"{data.get('body', '')[:85]}...\"")

    # 6B: Merchant Modification ("Can we change discount to 15% instead?")
    m_mod_conv = f"conv_m_mod_{int(time.time())}"
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
    print(f"         Snippet: \"{data.get('body', '')[:85]}...\"")

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
    print(f"         Snippet: \"{data.get('body', '')[:85]}...\"")

    # 6D: Merchant Rejection ("Don't post, cancel this draft")
    m_turn4_body = {
        "conversation_id": f"conv_m_rej_{int(time.time())}",
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
        print(f"\n{Colors.GREEN}{Colors.BOLD}>>> ALL 12/12 LIVE API SMOKE TESTS PASSED PERFECTLY ON RENDER! <<<{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}>>> SOME SMOKE TESTS FAILED. INSPECT LOGS ABOVE. <<<{Colors.RESET}\n")

    return all_passed

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    success = run_smoke_test(target)
    sys.exit(0 if success else 1)
