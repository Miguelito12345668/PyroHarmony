from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import RealtimeResponse, FirePoint
from app.services.zones import get_zone
from app.services.data_loader_cameroun import fetch_recent
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