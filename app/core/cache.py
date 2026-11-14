import time
from typing import Any, Optional

_store: dict[str, tuple[Any, float]] = {}


def get(key: str, ttl: int) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.time() - ts > ttl:
        del _store[key]
        return None
    return value


def set(key: str, value: Any) -> None:
    _store[key] = (value, time.time())


def clear() -> None:
    _store.clear()


def stats() -> dict:
    return {"entries": len(_store), "keys": list(_store.keys())}
