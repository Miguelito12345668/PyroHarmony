from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import CalendarResponse
from app.services.zones import get_zone
from app.services.data_loader_cameroun import get_cached_archive
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

    # Années jusqu'en 2027 pour inclure le Parquet harmonisé
    years = list(range(settings.start_year, 2027))
    
    # ⚠️ RETOUR TUPLE : rows (liste de feux) et scaling_ratio (float)
    rows, scaling_ratio = await get_cached_archive(zone, zone_cfg, years)
    
    result = build_calendar(rows, zone, settings.start_year)
    result["display_name"] = zone_cfg["display_name"]
    
    # ⚠️ Ajout du facteur d'échelle dans la réponse pour la traçabilité
    result["scaling_ratio"] = round(scaling_ratio, 4)
    
    cache.set(cache_key, result)
    return CalendarResponse(**result)