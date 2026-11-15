import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.settings import settings
from app.core import cache
from app.services.zones import list_enabled_zones
from app.services.data_loader_cameroun import get_cached_archive
from app.services.aggregator import build_calendar
from app.routers import zones, calendar, realtime, export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Préchargement au démarrage.
    Charge TOUS les points chauds (CSV historiques + Parquet harmonisé).
    """
    logger.info("=" * 60)
    logger.info("Démarrage PyroHarmony — préchargement (hybride CSV + Parquet)...")
    logger.info("=" * 60)

    years = list(range(settings.start_year, 2027))

    for z in list_enabled_zones():
        zone_id = z["id"]
        if not z.get("archive_country_name"):
            logger.info(f"[SKIP] {zone_id} (pas de pays archive)")
            continue

        try:
            logger.info(f"[LOAD] {zone_id} — années {min(years)}-{max(years)}")
            rows, scaling_ratio = await get_cached_archive(zone_id, z, years)
            result = build_calendar(rows, zone_id, settings.start_year)
            result["display_name"] = z["display_name"]
            result["scaling_ratio"] = round(scaling_ratio, 4)
            cache.set(f"calendar:{zone_id}", result)
            logger.info(
                f"[OK] {zone_id}: {result['total_fires']} feux "
                f"(MODIS: {result.get('total_modis', 0)}, "
                f"VIIRS: {result.get('total_viirs', 0)}, "
                f"ratio: {result['scaling_ratio']})"
            )
        except Exception as e:
            logger.error(f"[FAIL] {zone_id}: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info("Préchargement terminé.")
    logger.info("=" * 60)
    yield
    logger.info("Arrêt de PyroHarmony.")


app = FastAPI(
    title="PyroHarmony — Surveillance des feux par satellite",
    description=(
        "Plateforme d'harmonisation des points chauds MODIS et VIIRS "
        "pour la surveillance des feux au Cameroun."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS ouvert pour le hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers API ---
app.include_router(zones.router)
app.include_router(calendar.router)
app.include_router(realtime.router)
app.include_router(export.router)


# --- Frontend ---
# Chemin robuste : remonte depuis app/main.py vers la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent
_frontend = BASE_DIR / "frontend"

logger.info("=" * 60)
logger.info("MONTAGE DU FRONTEND")
logger.info(f"Racine du projet : {BASE_DIR}")
logger.info(f"Dossier frontend : {_frontend} (existe: {_frontend.exists()})")

if _frontend.exists():
    # 1. Dashboard (index.html + 3d.html) sur /ui
    app.mount("/ui", StaticFiles(directory=str(_frontend), html=True), name="ui")
    logger.info(f"✅ Dashboard monté sur /ui")

    # 2. Site vitrine sur /site
    _site = _frontend / "site"
    logger.info(f"Dossier site : {_site} (existe: {_site.exists()})")
    if _site.exists():
        app.mount("/site", StaticFiles(directory=str(_site), html=True), name="site")
        logger.info(f"✅ Site vitrine monté sur /site")
    else:
        logger.warning(f"⚠️ Dossier site introuvable : {_site}")
else:
    logger.warning(f"⚠️ Dossier frontend introuvable : {_frontend}")

logger.info("=" * 60)


@app.get("/", include_in_schema=False)
def root():
    """Redirige la racine vers le site vitrine."""
    return RedirectResponse(url="/site/")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "name": "PyroHarmony",
        "version": "1.0.0",
        "cache": cache.stats(),
    }