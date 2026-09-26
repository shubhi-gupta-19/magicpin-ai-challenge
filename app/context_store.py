import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

VALID_SCOPES = {"category", "merchant", "customer", "trigger"}

class ContextRecord:
    def __init__(self, scope: str, context_id: str, version: int, payload: dict[str, Any], delivered_at: Optional[str] = None):
        self.scope = scope
        self.context_id = context_id
        self.version = version
        self.payload = payload
        self.delivered_at = delivered_at or datetime.now(timezone.utc).isoformat()
        self.stored_at = datetime.now(timezone.utc).isoformat()

class ContextStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._contexts: dict[Tuple[str, str], ContextRecord] = {}

    def push(self, scope: str, context_id: str, version: int, payload: dict[str, Any], delivered_at: Optional[str] = None) -> Tuple[bool, Optional[str], int]:
        """
        Returns (success, reason, current_or_new_version).
        If version is stale or duplicate (current >= version), returns (False, 'stale_version', current_version).
        If version is strictly higher (or not present), updates store and returns (True, None, version).
        """
        if scope not in VALID_SCOPES:
            return False, "invalid_scope", 0

        with self._lock:
            key = (scope, context_id)
            current = self._contexts.get(key)
            if current and current.version >= version:
                return False, "stale_version", current.version
            
            record = ContextRecord(scope, context_id, version, payload, delivered_at)
            self._contexts[key] = record
            return True, None, version

    def get(self, scope: str, context_id: Optional[str]) -> Optional[dict[str, Any]]:
        """Retrieve payload for a given scope and context_id."""
        if not context_id:
            return None
        with self._lock:
            record = self._contexts.get((scope, context_id))
            return record.payload if record else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        with self._lock:
            record = self._contexts.get((scope, context_id))
            return record.version if record else None

    def get_counts(self) -> dict[str, int]:
        with self._lock:
            counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
            for (scope, _), _ in self._contexts.items():
                if scope in counts:
                    counts[scope] += 1
            return counts

    def get_all(self, scope: str) -> list[dict[str, Any]]:
        with self._lock:
            return [rec.payload for (s, _), rec in self._contexts.items() if s == scope]

    def clear(self):
        with self._lock:
            self._contexts.clear()

    def preload_from_dir(self, directory: Path):
        """Preload base categories, merchants, customers, triggers from a directory."""
        if not directory.exists():
            return
        
        # Load categories
        cat_dir = directory / "categories"
        if cat_dir.exists():
            for f in cat_dir.glob("*.json"):
                try:
                    with open(f, encoding="utf-8") as fp:
                        data = json.load(fp)
                        slug = data.get("slug", f.stem)
                        self.push("category", slug, 1, data)
                except Exception:
                    pass

        # Load merchants
        merchant_dir = directory / "merchants"
        if merchant_dir.exists():
            for f in merchant_dir.glob("*.json"):
                try:
                    with open(f, encoding="utf-8") as fp:
                        data = json.load(fp)
                        mid = data.get("merchant_id", f.stem)
                        self.push("merchant", mid, 1, data)
                except Exception:
                    pass

        # Load customers
        customer_dir = directory / "customers"
        if customer_dir.exists():
            for f in customer_dir.glob("*.json"):
                try:
                    with open(f, encoding="utf-8") as fp:
                        data = json.load(fp)
                        cid = data.get("customer_id", f.stem)
                        self.push("customer", cid, 1, data)
                except Exception:
                    pass

        # Load triggers
        trigger_dir = directory / "triggers"
        if trigger_dir.exists():
            for f in trigger_dir.glob("*.json"):
                try:
                    with open(f, encoding="utf-8") as fp:
                        data = json.load(fp)
                        tid = data.get("id", f.stem)
                        self.push("trigger", tid, 1, data)
                except Exception:
                    pass

context_store = ContextStore()
