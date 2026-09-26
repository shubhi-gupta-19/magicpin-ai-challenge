import re
from typing import Any, Optional, Tuple

def get_owner_name(merchant: dict[str, Any], default: str = "") -> str:
    identity = merchant.get("identity", {})
    owner = identity.get("owner_first_name") or ""
    if not owner:
        # Try to extract from merchant name if starts with Dr. or similar
        m_name = identity.get("name", "")
        if m_name.startswith("Dr. "):
            parts = m_name.split()
            if len(parts) > 1:
                owner = parts[1].rstrip("'s")
    return owner or default

def get_salutation(merchant: dict[str, Any], category_slug: str) -> str:
    owner = get_owner_name(merchant)
    if category_slug == "dentists":
        if owner.startswith("Dr.") or owner.startswith("Dr "):
            return owner
        return f"Dr. {owner}" if owner else "Doctor"
    return owner if owner else "there"

def get_locality(merchant: dict[str, Any]) -> str:
    identity = merchant.get("identity", {})
    return identity.get("locality") or identity.get("city") or "your locality"

def get_business_name(merchant: dict[str, Any]) -> str:
    identity = merchant.get("identity", {})
    return identity.get("name", "your business")

def get_active_offer(merchant: dict[str, Any], category: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    offers = merchant.get("offers", [])
    for off in offers:
        if off.get("status") == "active":
            return off
    if category:
        cat_catalog = category.get("offer_catalog", [])
        if cat_catalog:
            return cat_catalog[0]
    return None

def is_hindi_preferred(target: dict[str, Any]) -> bool:
    # Target can be merchant or customer
    identity = target.get("identity", {})
    langs = identity.get("languages", [])
    pref = identity.get("language_pref", "")
    return "hi" in langs or "hi-en mix" in pref or pref == "hi"

def sanitize_for_whatsapp(text: str) -> str:
    # No URLs allowed as per competition rules (penalty -3)
    text = re.sub(r'https?://\S+', '', text)
    # Remove multiple spaces/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
