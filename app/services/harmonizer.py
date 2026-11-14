from typing import Any


def normalize_confidence(raw: Any) -> str:
    if raw is None:
        return "unknown"
    s = str(raw).strip().lower()
    if s in ("l", "low"):
        return "low"
    if s in ("n", "nominal"):
        return "nominal"
    if s in ("h", "high"):
        return "high"
    try:
        pct = float(raw)
    except (ValueError, TypeError):
        return "unknown"
    if pct < 30:
        return "low"
    if pct < 80:
        return "nominal"
    return "high"


def get_field(row: Any, *names: str, default=None):
    for name in names:
        if hasattr(row, name):
            v = getattr(row, name)
            if v is not None:
                return v
        if isinstance(row, dict) and name in row:
            return row[name]
    return default


def to_dict(row: Any, sensor: str) -> dict:
    instrument = get_field(row, "instrument", default=sensor)
    satellite = get_field(row, "satellite", default="")
    label = f"{instrument}/{satellite}".strip("/") if satellite else str(instrument)

    return {
        "latitude": float(get_field(row, "latitude", default=0.0)),
        "longitude": float(get_field(row, "longitude", default=0.0)),
        "acq_date": str(get_field(row, "acq_date", default=""))[:10],
        "acq_time": str(get_field(row, "acq_time", default="") or ""),
        "sensor": label or sensor,
        "confidence": normalize_confidence(get_field(row, "confidence")),
        "frp": _safe_float(get_field(row, "frp_mw", "frp")),
        "detection_type": _safe_int(get_field(row, "detection_type", "type")),
    }


def _safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
