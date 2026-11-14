import json
from functools import lru_cache
from app.core.settings import settings


@lru_cache(maxsize=1)
def load_zones() -> dict:
    with open(settings.zones_config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_zone(zone_id: str) -> dict:
    zones = load_zones()
    if zone_id not in zones:
        raise ValueError(f"Zone inconnue: {zone_id}")
    zone = zones[zone_id]
    if not zone.get("enabled", False):
        raise ValueError(f"Zone désactivée: {zone_id}")
    return zone


def list_enabled_zones() -> list[dict]:
    zones = load_zones()
    return [{"id": zid, **z} for zid, z in zones.items() if z.get("enabled", False)]
