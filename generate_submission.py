#!/usr/bin/env python3
"""
Official Submission Generator for magicpin AI Challenge
========================================================
Generates submission.jsonl from expanded/test_pairs.json by running
each test pair through the deterministic compose() engine.
Emits exactly 30 JSON lines with required fields:
  test_id, body, cta, send_as, suppression_key, rationale
"""

import json
from pathlib import Path
from bot import compose

def generate_submission(output_file: str = "submission.jsonl") -> int:
    test_pairs_path = Path("expanded/test_pairs.json")
    if not test_pairs_path.exists():
        raise FileNotFoundError(f"Fixture {test_pairs_path} not found. Run dataset generator first.")

    with open(test_pairs_path, encoding="utf-8") as f:
        pairs = json.load(f).get("pairs", [])

    output_path = Path(output_file)
    count = 0

    with open(output_path, "w", encoding="utf-8") as out:
        for item in pairs:
            test_id = item["test_id"]
            tid = item["trigger_id"]
            mid = item["merchant_id"]
            cid = item.get("customer_id")

            with open(f"expanded/merchants/{mid}.json", encoding="utf-8") as fp:
                merchant = json.load(fp)
            with open(f"expanded/triggers/{tid}.json", encoding="utf-8") as fp:
                trigger = json.load(fp)
            cat_slug = merchant.get("category_slug", "dentists")
            with open(f"expanded/categories/{cat_slug}.json", encoding="utf-8") as fp:
                category = json.load(fp)

            customer = None
            if cid:
                cust_path = Path(f"expanded/customers/{cid}.json")
                if cust_path.exists():
                    with open(cust_path, encoding="utf-8") as fp:
                        customer = json.load(fp)

            composed = compose(category, merchant, trigger, customer)

            record = {
                "test_id": test_id,
                "body": composed["body"],
                "cta": composed["cta"],
                "send_as": composed["send_as"],
                "suppression_key": composed["suppression_key"],
                "rationale": composed["rationale"]
            }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"[SUCCESS] Generated {count} canonical submission records in {output_path}")
    return count

if __name__ == "__main__":
    generate_submission()
