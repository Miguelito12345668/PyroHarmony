import logging
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


from pathlib import Path
from fastapi.staticfiles import StaticFiles

_frontend = Path("frontend")
if _frontend.exists():
    app.mount("/ui", StaticFiles(directory=str(_frontend), html=True), name="ui")
    
@app.get("/")
def root():
    return {"name": "MODIS_VIIRS", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "cache": cache.stats()}
