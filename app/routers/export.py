import csv
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services.zones import get_zone
from app.services.data_loader_cameroun import get_cached_archive
from app.services.harmonizer import to_dict
from app.core.settings import settings

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/csv")
async def export_csv(zone: str = Query(...)):
    try:
        zone_cfg = get_zone(zone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    years = list(range(settings.start_year, 2027))
    
    # ⚠️ RETOUR TUPLE : on ignore le ratio pour l'export
    rows, _ = await get_cached_archive(zone, zone_cfg, years)

    label = "+".join(zone_cfg.get("products_archive", ["FIRMS"]))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["latitude", "longitude", "acq_date", "acq_time",
                "sensor", "confidence", "frp", "detection_type"])
    
    for r in rows:
        # to_dict() gère les valeurs par défaut si certains champs manquent
        d = to_dict(r, label)
        w.writerow([d["latitude"], d["longitude"], d["acq_date"], d["acq_time"],
                    d["sensor"], d["confidence"], d["frp"], d["detection_type"]])
        
    out.seek(0)
    fname = f"fires_{zone}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})