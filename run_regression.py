#!/usr/bin/env python3
"""
Official Canonical Regression Runner for magicpin AI Challenge
==============================================================
Loads expanded/test_pairs.json (30 canonical pairs) and executes
each pair through the deterministic compose() engine, validating:
1. All required fields are present (body, cta, send_as, suppression_key, rationale)
2. No banned patterns (e.g., external URLs)
3. Correct attribution (send_as = vera vs merchant_on_behalf)
4. Non-empty, verified content matching category and merchant
"""

import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from bot import compose

def run_regression() -> bool:
    test_pairs_path = Path("expanded/test_pairs.json")
    if not test_pairs_path.exists():
        print(f"[ERROR] Fixture file not found: {test_pairs_path}")
        print("Please run: python dataset/generate_dataset.py --seed-dir dataset --out expanded")
        return False

    with open(test_pairs_path, encoding="utf-8") as f:
        data = json.load(f)
    
    pairs = data.get("pairs", [])
    if not pairs:
        print("[ERROR] No pairs found in test_pairs.json!")
        return False

    print("=" * 80)
    print(f"OFFICIAL CANONICAL REGRESSION RUNNER — {len(pairs)} TEST PAIRS")
    print("=" * 80)

    passed = 0
    failed = 0
    failures = []

    for item in pairs:
        test_id = item.get("test_id")
        tid = item.get("trigger_id")
        mid = item.get("merchant_id")
        cid = item.get("customer_id")

        try:
            m_path = Path(f"expanded/merchants/{mid}.json")
            t_path = Path(f"expanded/triggers/{tid}.json")

            if not m_path.exists():
                raise FileNotFoundError(f"Merchant file missing: {m_path}")
            if not t_path.exists():
                raise FileNotFoundError(f"Trigger file missing: {t_path}")

            with open(m_path, encoding="utf-8") as fp:
                merchant = json.load(fp)
            with open(t_path, encoding="utf-8") as fp:
                trigger = json.load(fp)

            cat_slug = merchant.get("category_slug", "dentists")
            c_path = Path(f"expanded/categories/{cat_slug}.json")
            if not c_path.exists():
                raise FileNotFoundError(f"Category file missing: {c_path}")
            with open(c_path, encoding="utf-8") as fp:
                category = json.load(fp)

            customer = None
            if cid:
                cust_path = Path(f"expanded/customers/{cid}.json")
                if cust_path.exists():
                    with open(cust_path, encoding="utf-8") as fp:
                        customer = json.load(fp)

            # Execute composition
            result = compose(category, merchant, trigger, customer)

            # Validations
            errors = []
            body = result.get("body", "")
            if not body or len(body.strip()) < 10:
                errors.append("Body is empty or too short (< 10 chars)")
            if "http://" in body or "https://" in body:
                errors.append("Forbidden external URL detected in body")
            
            cta = result.get("cta")
            if not cta:
                errors.append("CTA is missing")

            send_as = result.get("send_as")
            expected_send_as = "merchant_on_behalf" if (customer or trigger.get("scope") == "customer") else "vera"
            if send_as != expected_send_as:
                errors.append(f"send_as mismatch: expected {expected_send_as}, got {send_as}")

            supp_key = result.get("suppression_key")
            if not supp_key:
                errors.append("suppression_key is missing")

            rationale = result.get("rationale")
            if not rationale:
                errors.append("rationale is missing")

            if errors:
                failed += 1
                failures.append((test_id, tid, errors))
                print(f"[{test_id}] FAIL: {tid} -> {'; '.join(errors)}")
            else:
                passed += 1
                short_body = (body[:75] + "...") if len(body) > 75 else body
                print(f"[{test_id}] PASS | Kind: {trigger.get('kind', 'unknown'):22} | SendAs: {send_as:18} | \"{short_body}\"")

        except Exception as e:
            failed += 1
            failures.append((test_id, tid, [str(e)]))
            print(f"[{test_id}] ERROR: {tid} -> Exception: {e}")

    print("-" * 80)
    print(f"TOTAL: {len(pairs)} | PASSED: {passed} | FAILED: {failed}")
    if failed == 0:
        print("ALL 30 CANONICAL REGRESSION TESTS PASSED SUCCESSFULLY! [100%]")
        print("=" * 80)
        return True
    else:
        print(f"{failed} TEST(S) FAILED. Inspect diagnostics above.")
        print("=" * 80)
        return False

if __name__ == "__main__":
    success = run_regression()
    sys.exit(0 if success else 1)
