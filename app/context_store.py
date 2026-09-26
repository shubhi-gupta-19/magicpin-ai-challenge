import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

VALID_SCOPES = {"category", "merchant", "customer", "trigger"}
CACHE_FILE = Path("data/pushed_contexts.json")

class ContextRecord:
    def __init__(self, scope: str, context_id: str, version: int, payload: dict[str, Any], delivered_at: Optional[str] = None):
        self.scope = scope
        self.context_id = context_id
        self.version = version
        self.payload = payload
        self.delivered_at = delivered_at or datetime.now(timezone.utc).isoformat()
        self.stored_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "context_id": self.context_id,
            "version": self.version,
            "payload": self.payload,
            "delivered_at": self.delivered_at,
            "stored_at": self.stored_at
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContextRecord":
        rec = cls(d["scope"], d["context_id"], d["version"], d["payload"], d.get("delivered_at"))
        rec.stored_at = d.get("stored_at", rec.stored_at)
        return rec

class ContextStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._contexts: dict[Tuple[str, str], ContextRecord] = {}
        self._disk_cache: dict[Tuple[str, str], dict[str, Any]] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        rec = ContextRecord.from_dict(item)
                        self._contexts[(rec.scope, rec.context_id)] = rec
        except Exception:
            pass

    def _save_to_disk(self):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                data = [rec.to_dict() for rec in self._contexts.values()]
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

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
            self._save_to_disk()
            return True, None, version

    def get(self, scope: str, context_id: Optional[str]) -> Optional[dict[str, Any]]:
        """Retrieve payload for a given scope and context_id, with disk fallback if not in pushed contexts."""
        if not context_id:
            return None
        with self._lock:
            # 1. Pushed context takes priority
            record = self._contexts.get((scope, context_id))
            if record:
                return record.payload

            # 2. Check cached fallback
            if (scope, context_id) in self._disk_cache:
                return self._disk_cache[(scope, context_id)]

            # 3. Fallback to expanded or dataset directory
            payload = self._find_on_disk(scope, context_id)
            if payload:
                self._disk_cache[(scope, context_id)] = payload
                return payload

            return None

    def _find_on_disk(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        dirs = [Path("expanded"), Path("dataset")]
        q = context_id.lower().strip()
        subdir_name = f"{scope}s" if scope != "category" else "categories"

        # 1. Direct file check
        for base in dirs:
            direct_path = base / subdir_name / f"{context_id}.json"
            if direct_path.exists():
                try:
                    with open(direct_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        # 2. Scope-specific searches
        if scope == "trigger":
            kind_aliases = {
                "appointment_reminder": "appointment_tomorrow",
                "appointment": "appointment_tomorrow",
                "post_visit_followup": "recall_due",
                "followup": "recall_due",
                "winback": "customer_lapsed_hard",
                "lapsed": "customer_lapsed_soft",
                "refill": "chronic_refill_due",
                "diwali": "festival_upcoming",
                "ipl": "ipl_match_today",
                "cde": "cde_opportunity",
                "competitor": "competitor_opened",
                "milestone": "milestone_reached",
                "perf_dip": "perf_dip",
                "perf_spike": "perf_spike",
                "dormant": "dormant_with_vera",
                "active_planning": "active_planning_intent",
            }
            target_kind = kind_aliases.get(q, q)
            for base in dirs:
                trg_dir = base / "triggers"
                if trg_dir.exists():
                    for f in trg_dir.glob("*.json"):
                        try:
                            with open(f, "r", encoding="utf-8") as fp:
                                data = json.load(fp)
                                if (data.get("id") == context_id or
                                    data.get("kind") == target_kind or                                    target_kind in data.get("kind", "") or
                                    q in f.stem.lower() or
                                    q in data.get("id", "").lower()):
                                    return data
                        except Exception:
                            pass
        elif scope == "merchant":
            for base in dirs:
                m_dir = base / "merchants"
                if m_dir.exists():
                    for f in m_dir.glob("*.json"):
                        stem_lower = f.stem.lower()
                        if q == stem_lower or q in stem_lower or stem_lower.startswith(q):
                            try:
                                with open(f, "r", encoding="utf-8") as fp:
                                    data = json.load(fp)
                                    if data.get("merchant_id") == context_id or q in f.stem.lower():
                                        return data
                            except Exception:
                                pass
        elif scope == "customer":
            for base in dirs:
                c_dir = base / "customers"
                if c_dir.exists():
                    for f in c_dir.glob("*.json"):
                        stem_lower = f.stem.lower()
                        if q == stem_lower or q in stem_lower or stem_lower.startswith(q):
                            try:
                                with open(f, "r", encoding="utf-8") as fp:
                                    data = json.load(fp)
                                    if data.get("customer_id") == context_id or q in f.stem.lower():
                                        return data
                            except Exception:
                                pass
        elif scope == "category":
            for base in dirs:
                cat_dir = base / "categories"
                if cat_dir.exists():
                    for f in cat_dir.glob("*.json"):
                        stem_lower = f.stem.lower()
                        if q == stem_lower or q in stem_lower:
                            try:
                                with open(f, "r", encoding="utf-8") as fp:
                                    data = json.load(fp)
                                    if data.get("slug") == context_id or q in f.stem.lower():
                                        return data
                            except Exception:
                                pass

        return None

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
            pushed = [rec.payload for (s, _), rec in self._contexts.items() if s == scope]
            if pushed:
                return pushed
            # Fallback to loading all available from disk if none pushed
            items = []
            subdir_name = f"{scope}s" if scope != "category" else "categories"
            for base in [Path("expanded"), Path("dataset")]:
                p = base / subdir_name
                if p.exists():
                    for f in p.glob("*.json"):
                        try:
                            with open(f, "r", encoding="utf-8") as fp:
                                items.append(json.load(fp))
                        except Exception:
                            pass
                    if items:
                        break
            return items

    def clear(self):
        with self._lock:
            self._contexts.clear()
            self._disk_cache.clear()
            if CACHE_FILE.exists():
                try:
                    CACHE_FILE.unlink()
                except Exception:
                    pass

context_store = ContextStore()
