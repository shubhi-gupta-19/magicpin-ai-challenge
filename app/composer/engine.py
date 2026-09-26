from typing import Any, Optional
from app.composer.strategies import STRATEGY_MAP
from app.composer.base import sanitize_for_whatsapp

def compose(category: dict[str, Any], merchant: dict[str, Any], trigger: dict[str, Any], customer: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Deterministic composition engine based on 4-context framework.
    Guarantees deterministic, category-specific, non-hallucinated copy.
    """
    category = category or {}
    merchant = merchant or {}
    trigger = trigger or {}

    slug = merchant.get("category_slug") or category.get("slug") or "dentists"
    strategy_cls = STRATEGY_MAP.get(slug, STRATEGY_MAP["dentists"])

    res = strategy_cls.compose(category, merchant, trigger, customer)
    
    # Ensure all required fields exist
    body = sanitize_for_whatsapp(res.get("body", ""))
    cta = res.get("cta", "binary_yes_no")
    
    # Determine send_as
    scope = trigger.get("scope", "merchant")
    default_send_as = "merchant_on_behalf" if (customer or scope == "customer") else "vera"
    send_as = res.get("send_as", default_send_as)
    
    suppression_key = res.get("suppression_key") or trigger.get("suppression_key") or f"{trigger.get('kind', 'event')}:{merchant.get('merchant_id', 'm0')}"
    rationale = res.get("rationale", "Composed deterministically using category, merchant, and trigger contexts.")
    template_name = res.get("template_name", f"vera_{slug}_touch_v1")
    template_params = res.get("template_params", [merchant.get("identity", {}).get("name", "Merchant")])

    return {
        "body": body,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": suppression_key,
        "rationale": rationale,
        "template_name": template_name,
        "template_params": template_params,
    }
