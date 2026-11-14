"""Génère toute l'arborescence et les fichiers du projet MODIS_VIIRS."""
from pathlib import Path

BASE = Path(__file__).parent

FILES = {
    "app/config/__init__.py": "",
    "app/config/zones.json": """{
  "cameroun": {
    "display_name": "Cameroun",
    "bbox": [8.5, 1.6, 16.2, 13.1],
    "archive_country_name": "Cameroon",
    "products_archive": ["MODIS", "VIIRS_SNPP"],
    "products_realtime": ["MODIS_NRT", "VIIRS_SNPP_NRT"],
    "enabled": true
  },
  "afrique_centrale": {
    "display_name": "Afrique Centrale",
    "bbox": [8.0, -6.0, 19.0, 13.5],
    "archive_country_name": null,
    "products_archive": ["MODIS", "VIIRS_SNPP"],
    "products_realtime": ["MODIS_NRT", "VIIRS_SNPP_NRT"],
    "enabled": false
  }
}
""",
    "app/core/__init__.py": "",
    "app/core/settings.py": """from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    firms_map_key: str = ""
    cache_dir: Path = Path("./cache")
    cache_ttl_seconds: int = 21600
    start_year: int = 2000
    zones_config_path: Path = Path("app/config/zones.json")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
""",
    "app/core/cache.py": """import time
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
""",
    "app/models/__init__.py": "",
    "app/models/schemas.py": """from pydantic import BaseModel


class ZoneInfo(BaseModel):
    id: str
    display_name: str
    bbox: list[float]
    enabled: bool


class ZonesResponse(BaseModel):
    zones: list[ZoneInfo]


class CalendarResponse(BaseModel):
    zone: str
    display_name: str
    years: list[int]
    months: list[int]
    matrix: list[list[int]]
    median_by_month: list[float]
    current_year: int
    current_month: int
    current_count: int
    median_for_current_month: float
    current_anomaly_pct: float
    total_fires: int
    sensors_used: list[str]
    generated_at: str


class FirePoint(BaseModel):
    latitude: float
    longitude: float
    acq_date: str
    acq_time: str | None = None
    sensor: str
    confidence: str
    frp: float | None = None
    detection_type: int | None = None


class RealtimeResponse(BaseModel):
    zone: str
    days: int
    count: int
    fires: list[FirePoint]
    generated_at: str
""",
    "app/services/__init__.py": "",
    "app/services/zones.py": """import json
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
""",
    "app/services/data_loader.py": '''import logging
from typing import Any
import httpx

from app.core.settings import settings
from app.core import cache

logger = logging.getLogger(__name__)

try:
    import firms_client
    from firms_client import fetch_archive, fetch_area, select, ARCHIVE_PRODUCTS
    FIRMS_CLIENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"firms-client non disponible: {e}")
    FIRMS_CLIENT_AVAILABLE = False
    ARCHIVE_PRODUCTS = []


_PRODUCT_SLUG_MAP = {
    "MODIS": "modis",
    "VIIRS_SNPP": "viirs-snpp",
    "VIIRS_NOAA20": "viirs-noaa20",
    "VIIRS_NOAA21": "viirs-noaa21",
}


def _resolve_archive_product(name: str):
    if not FIRMS_CLIENT_AVAILABLE:
        return name
    slug = _PRODUCT_SLUG_MAP.get(name.upper(), name.lower())
    for p in ARCHIVE_PRODUCTS:
        if getattr(p, "slug", None) == slug:
            return p
    return name


async def fetch_archive_years(zone: dict, years: list[int]) -> list[Any]:
    if not FIRMS_CLIENT_AVAILABLE:
        raise RuntimeError("firms-client n'est pas installé")
    country = zone.get("archive_country_name")
    if not country:
        raise ValueError("Zone sans nom de pays d'archive")

    product_names = zone.get("products_archive", ["MODIS", "VIIRS_SNPP"])
    all_rows: list[Any] = []

    async with httpx.AsyncClient(timeout=180) as client:
        for product_name in product_names:
            product = _resolve_archive_product(product_name)
            for year in years:
                try:
                    rows = await fetch_archive(client, product, year, country)
                except Exception as e:
                    logger.warning(f"Échec {product_name}/{year}: {e}")
                    continue
                if not rows:
                    continue
                try:
                    filtered = select(rows, vegetation_only=True, min_confidence="nominal")
                except Exception as e:
                    logger.warning(f"select() échoué {product_name}/{year}: {e}")
                    filtered = rows
                all_rows.extend(filtered)
                logger.info(f"{product_name}/{year}/{country}: {len(filtered)} feux")
    return all_rows


async def fetch_recent(zone: dict, days: int = 3) -> list[Any]:
    if not FIRMS_CLIENT_AVAILABLE:
        raise RuntimeError("firms-client n'est pas installé")
    if not settings.firms_map_key:
        raise RuntimeError("FIRMS_MAP_KEY non configurée")

    products = zone.get("products_realtime", [])
    bbox = tuple(zone["bbox"])
    all_rows: list[Any] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for product in products:
            try:
                rows = await fetch_area(client, settings.firms_map_key, product, bbox, days=days)
            except Exception as e:
                logger.warning(f"Échec realtime {product}: {e}")
                continue
            if rows:
                try:
                    filtered = select(rows, min_frp_mw=1.0)
                except Exception:
                    filtered = rows
                all_rows.extend(filtered)
    return all_rows


async def get_cached_archive(zone_id: str, zone: dict, years: list[int]):
    """Version async — obligatoire pour être appelée depuis lifespan ou router async."""
    key = f"archive:{zone_id}:{min(years)}:{max(years)}"
    cached = cache.get(key, settings.cache_ttl_seconds)
    if cached is not None:
        logger.info(f"Cache HIT {key}")
        return cached

    rows = await fetch_archive_years(zone, years)
    cache.set(key, rows)
    return rows
''',
    "app/services/harmonizer.py": '''from typing import Any


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
''',
    "app/services/aggregator.py": """from datetime import datetime
from collections import defaultdict
import statistics


def build_calendar(rows: list, zone_id: str, start_year: int) -> dict:
    counts: dict[tuple[int, int], int] = defaultdict(int)
    sensors_seen: set[str] = set()
    valid_years: set[int] = set()

    for row in rows:
        date_str = _extract_date(row)
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if dt.year < start_year:
            continue
        counts[(dt.year, dt.month)] += 1
        valid_years.add(dt.year)
        sensors_seen.add(_extract_sensor(row))

    if not valid_years:
        return _empty(zone_id, start_year)

    years = list(range(min(valid_years), max(valid_years) + 1))
    months = list(range(1, 13))
    matrix = [[counts.get((y, m), 0) for m in months] for y in years]

    median_by_month = []
    for m_idx in range(12):
        values = [matrix[y_idx][m_idx] for y_idx in range(len(years))]
        median_by_month.append(float(statistics.median(values)) if values else 0.0)

    current_year = max(valid_years)
    current_month = _last_month(counts, current_year)
    current_count = counts.get((current_year, current_month), 0)
    median_current = median_by_month[current_month - 1]
    anomaly_pct = (
        ((current_count - median_current) / median_current * 100)
        if median_current > 0 else 0.0
    )

    return {
        "zone": zone_id, "display_name": zone_id,
        "years": years, "months": months, "matrix": matrix,
        "median_by_month": median_by_month,
        "current_year": current_year, "current_month": current_month,
        "current_count": current_count,
        "median_for_current_month": median_current,
        "current_anomaly_pct": round(anomaly_pct, 1),
        "total_fires": sum(sum(r) for r in matrix),
        "sensors_used": sorted(sensors_seen),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _extract_date(row) -> str:
    for attr in ("acq_date", "date"):
        v = getattr(row, attr, None) if hasattr(row, attr) else None
        if v is None and isinstance(row, dict):
            v = row.get(attr)
        if v:
            return str(v)
    return ""


def _extract_sensor(row) -> str:
    for attr in ("instrument", "sensor", "satellite"):
        v = getattr(row, attr, None) if hasattr(row, attr) else None
        if v is None and isinstance(row, dict):
            v = row.get(attr)
        if v:
            return str(v).upper()
    return "UNKNOWN"


def _last_month(counts, year) -> int:
    months = [m for (y, m) in counts if y == year]
    return max(months) if months else 12


def _empty(zone_id, start_year) -> dict:
    return {
        "zone": zone_id, "display_name": zone_id,
        "years": [], "months": list(range(1, 13)), "matrix": [],
        "median_by_month": [0.0] * 12,
        "current_year": start_year, "current_month": 1,
        "current_count": 0, "median_for_current_month": 0.0,
        "current_anomaly_pct": 0.0, "total_fires": 0,
        "sensors_used": [], "generated_at": datetime.utcnow().isoformat() + "Z",
    }
""",
    "app/routers/__init__.py": "",
    "app/routers/zones.py": """from fastapi import APIRouter
from app.models.schemas import ZonesResponse, ZoneInfo
from app.services.zones import list_enabled_zones

router = APIRouter(prefix="/api", tags=["zones"])


@router.get("/zones", response_model=ZonesResponse)
def get_zones():
    return ZonesResponse(zones=[
        ZoneInfo(id=z["id"], display_name=z["display_name"],
                 bbox=z["bbox"], enabled=z["enabled"])
        for z in list_enabled_zones()
    ])
""",
    "app/routers/calendar.py": """from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import CalendarResponse
from app.services.zones import get_zone
from app.services.data_loader import get_cached_archive
from app.services.aggregator import build_calendar
from app.core.settings import settings
from app.core import cache

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/calendar", response_model=CalendarResponse)
async def get_calendar(zone: str = Query(...)):
    try:
        zone_cfg = get_zone(zone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    cache_key = f"calendar:{zone}"
    cached = cache.get(cache_key, settings.cache_ttl_seconds)
    if cached:
        return CalendarResponse(**cached)

    years = list(range(settings.start_year, 2026))
    rows = await get_cached_archive(zone, zone_cfg, years)
    result = build_calendar(rows, zone, settings.start_year)
    result["display_name"] = zone_cfg["display_name"]
    cache.set(cache_key, result)
    return CalendarResponse(**result)
""",
    "app/routers/realtime.py": """from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import RealtimeResponse, FirePoint
from app.services.zones import get_zone
from app.services.data_loader import fetch_recent
from app.services.harmonizer import to_dict

router = APIRouter(prefix="/api", tags=["realtime"])


@router.get("/realtime", response_model=RealtimeResponse)
async def get_realtime(zone: str = Query(...), days: int = Query(3, ge=1, le=5)):
    try:
        zone_cfg = get_zone(zone)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        rows = await fetch_recent(zone_cfg, days=days)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    label = "+".join(zone_cfg.get("products_realtime", ["FIRMS"]))
    fires = [FirePoint(**to_dict(r, label)) for r in rows]
    return RealtimeResponse(
        zone=zone, days=days, count=len(fires), fires=fires,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )
""",
    "app/routers/export.py": """import csv, io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services.zones import get_zone
from app.services.data_loader import get_cached_archive
from app.services.harmonizer import to_dict
from app.core.settings import settings

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/csv")
async def export_csv(zone: str = Query(...)):
    try:
        zone_cfg = get_zone(zone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    years = list(range(settings.start_year, 2026))
    rows = await get_cached_archive(zone, zone_cfg, years)

    label = "+".join(zone_cfg.get("products_archive", ["FIRMS"]))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["latitude", "longitude", "acq_date", "acq_time",
                "sensor", "confidence", "frp", "detection_type"])
    for r in rows:
        d = to_dict(r, label)
        w.writerow([d["latitude"], d["longitude"], d["acq_date"], d["acq_time"],
                    d["sensor"], d["confidence"], d["frp"], d["detection_type"]])
    out.seek(0)
    fname = f"fires_{zone}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})
""",
    "app/main.py": """import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.services.zones import list_enabled_zones
from app.services.data_loader import get_cached_archive
from app.services.aggregator import build_calendar
from app.core import cache
from app.routers import zones, calendar, realtime, export

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage MODIS_VIIRS — préchargement...")
    years = list(range(settings.start_year, 2026))
    for z in list_enabled_zones():
        zone_id = z["id"]
        if not z.get("archive_country_name"):
            logger.info(f"[SKIP] {zone_id} (pas de pays archive)")
            continue
        try:
            logger.info(f"[LOAD] {zone_id} {min(years)}-{max(years)}")
            rows = await get_cached_archive(zone_id, z, years)
            result = build_calendar(rows, zone_id, settings.start_year)
            result["display_name"] = z["display_name"]
            cache.set(f"calendar:{zone_id}", result)
            logger.info(f"[OK] {zone_id}: {result['total_fires']} feux")
        except Exception as e:
            logger.error(f"[FAIL] {zone_id}: {e}", exc_info=True)
    yield


app = FastAPI(title="MODIS_VIIRS", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(zones.router)
app.include_router(calendar.router)
app.include_router(realtime.router)
app.include_router(export.router)


@app.get("/")
def root():
    return {"name": "MODIS_VIIRS", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "cache": cache.stats()}
""",
    "scripts/test_pipeline.py": """import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.zones import get_zone
from app.services.data_loader import fetch_archive_years
from app.services.aggregator import build_calendar
from app.services.harmonizer import to_dict


async def main():
    print("=" * 60)
    print("TEST PIPELINE — Cameroun")
    print("=" * 60)
    zone = get_zone("cameroun")
    print(f"Zone: {zone['display_name']}, pays: {zone['archive_country_name']}")
    rows = await fetch_archive_years(zone, [2023, 2024])
    print(f"\\n{len(rows)} feux récupérés")
    if rows:
        r0 = rows[0]
        print(f"\\nAttributs Hotspot: {[a for a in dir(r0) if not a.startswith('_')][:15]}")
        print(f"Premier (normalisé): {to_dict(r0, 'test')}")
        r = build_calendar(rows, "cameroun", 2023)
        print(f"\\nTotal: {r['total_fires']}")
        print(f"Capteurs: {r['sensors_used']}")
        print(f"Années: {r['years']}")
        print(f"Médiane janv-déc: {[round(x, 1) for x in r['median_by_month']]}")
        print("\\nPIPELINE VALIDÉ")
    else:
        print("AUCUNE DONNÉE")


if __name__ == "__main__":
    asyncio.run(main())
""",
    "app/__init__.py": "",
    ".env.example": "FIRMS_MAP_KEY=\nCACHE_DIR=./cache\nCACHE_TTL_SECONDS=21600\nSTART_YEAR=2000\n",
    ".gitignore": ".env\n__pycache__/\n*.pyc\ncache/\n.venv/\nvenv/\n*.log\n",
}

for path_str, content in FILES.items():
    path = BASE / path_str
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"OK {path_str}")

print(f"\n{len(FILES)} fichiers créés.")