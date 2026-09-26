import threading
from datetime import datetime, timezone
from typing import Optional

def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

class SuppressionManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._suppressed: dict[str, Optional[datetime]] = {}

    def is_suppressed(self, key: Optional[str], now_str: Optional[str] = None) -> bool:
        if not key:
            return False
        with self._lock:
            if key not in self._suppressed:
                return False
            expires_at = self._suppressed[key]
            if expires_at is None:
                return True
            now_dt = parse_iso(now_str) or datetime.now(timezone.utc)
            if now_dt < expires_at:
                return True
            # Expired, clean up
            del self._suppressed[key]
            return False

    def suppress(self, key: Optional[str], expires_at_str: Optional[str] = None, now_str: Optional[str] = None):
        if not key:
            return
        with self._lock:
            now_dt = parse_iso(now_str) or datetime.now(timezone.utc)
            expires_at = parse_iso(expires_at_str)
            if expires_at is None or expires_at <= now_dt:
                from datetime import timedelta
                expires_at = now_dt + timedelta(days=7)
            self._suppressed[key] = expires_at

    def clear(self):
        with self._lock:
            self._suppressed.clear()

suppression_manager = SuppressionManager()
