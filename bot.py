"""
magicpin AI Challenge — Vera Bot Entry Point
=============================================
Exposes:
1. `app`: FastAPI application exposing the 5 official endpoints (/v1/*)
2. `compose(category, merchant, trigger, customer=None)`: Core deterministic composition function

Run locally:
    uvicorn bot:app --host 0.0.0.0 --port 8080
"""

from typing import Any, Optional
from app.main import app
from app.composer import compose as app_compose

def compose(category: dict[str, Any], merchant: dict[str, Any], trigger: dict[str, Any], customer: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Inputs are dicts loaded from the dataset JSON.
    Returns a dict with keys: body, cta, send_as, suppression_key, rationale,
    plus template_name and template_params for WhatsApp first-touch compliance.
    """
    return app_compose(category, merchant, trigger, customer)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=True)
