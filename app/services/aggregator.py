"""
Construit la matrice calendrier (année × mois) avec séparation MODIS / VIIRS.

Pourquoi séparer les deux capteurs ?
- MODIS existe depuis 2000, VIIRS depuis 2012.
- VIIRS détecte 3 à 5× plus de feux que MODIS (résolution 375 m vs 1 km).
- Sans séparation, on observe un "pic artificiel" en 2012 qui n'est PAS
  une augmentation réelle des incendies, mais l'ajout d'un capteur plus sensible.
- En exposant matrix_modis et matrix_viirs séparément, le frontend peut
  afficher les deux séries empilées ou côte à côte et expliquer la discontinuité.
"""
from datetime import datetime
from collections import defaultdict
import statistics


def build_calendar(rows: list, zone_id: str, start_year: int) -> dict:
    # --- 1. Compter par (année, mois) et par capteur ---
    counts_modis: dict[tuple[int, int], int] = defaultdict(int)
    counts_viirs: dict[tuple[int, int], int] = defaultdict(int)
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

        valid_years.add(dt.year)
        key = (dt.year, dt.month)
        instrument = _extract_instrument(row)

        if "VIIRS" in instrument:
            counts_viirs[key] += 1
        else:
            # MODIS ou inconnu → compté dans MODIS par défaut
            counts_modis[key] += 1

    if not valid_years:
        return _empty(zone_id, start_year)

    # --- 2. Construire les 3 matrices ---
    years = list(range(min(valid_years), max(valid_years) + 1))
    months = list(range(1, 13))

    matrix_modis = [[counts_modis.get((y, m), 0) for m in months] for y in years]
    matrix_viirs = [[counts_viirs.get((y, m), 0) for m in months] for y in years]
    matrix = [
        [matrix_modis[i][j] + matrix_viirs[i][j] for j in range(12)]
        for i in range(len(years))
    ]

    # --- 3. Médiane par mois sur la matrice COMBINÉE ---
    median_by_month = []
    for m_idx in range(12):
        values = [matrix[y_idx][m_idx] for y_idx in range(len(years))]
        median_by_month.append(float(statistics.median(values)) if values else 0.0)

    # --- 4. Première année où VIIRS apparaît ---
    first_viirs_year = None
    for i, y in enumerate(years):
        if any(matrix_viirs[i]):
            first_viirs_year = y
            break

    # --- 5. Anomalie du mois le plus récent ---
    current_year = max(valid_years)
    current_month = _last_month(counts_modis, counts_viirs, current_year)
    current_count = matrix[years.index(current_year)][current_month - 1]
    median_current = median_by_month[current_month - 1]
    anomaly_pct = (
        ((current_count - median_current) / median_current * 100)
        if median_current > 0 else 0.0
    )

    # --- 6. Réponse ---
    return {
        "zone": zone_id,
        "display_name": zone_id,
        "years": years,
        "months": months,
        "matrix": matrix,
        "matrix_modis": matrix_modis,
        "matrix_viirs": matrix_viirs,
        "first_viirs_year": first_viirs_year,
        "median_by_month": median_by_month,
        "current_year": current_year,
        "current_month": current_month,
        "current_count": current_count,
        "median_for_current_month": median_current,
        "current_anomaly_pct": round(anomaly_pct, 1),
        "total_fires": sum(sum(r) for r in matrix),
        "total_modis": sum(sum(r) for r in matrix_modis),
        "total_viirs": sum(sum(r) for r in matrix_viirs),
        "sensors_used": _sensors_list(matrix_modis, matrix_viirs),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================
# Helpers
# ============================================================

def _extract_date(row) -> str:
    for attr in ("acq_date", "date"):
        v = getattr(row, attr, None) if hasattr(row, attr) else None
        if v is None and isinstance(row, dict):
            v = row.get(attr)
        if v:
            return str(v)
    return ""


def _extract_instrument(row) -> str:
    v = getattr(row, "instrument", None) if hasattr(row, "instrument") else None
    if v is None and isinstance(row, dict):
        v = row.get("instrument")
    return str(v).upper() if v else "UNKNOWN"


def _sensors_list(matrix_modis, matrix_viirs) -> list[str]:
    out = []
    if any(any(r) for r in matrix_modis):
        out.append("MODIS")
    if any(any(r) for r in matrix_viirs):
        out.append("VIIRS")
    return out


def _last_month(counts_modis, counts_viirs, year) -> int:
    months = [m for (y, m) in list(counts_modis) + list(counts_viirs) if y == year]
    return max(months) if months else 12


def _empty(zone_id: str, start_year: int) -> dict:
    return {
        "zone": zone_id,
        "display_name": zone_id,
        "years": [],
        "months": list(range(1, 13)),
        "matrix": [],
        "matrix_modis": [],
        "matrix_viirs": [],
        "first_viirs_year": None,
        "median_by_month": [0.0] * 12,
        "current_year": start_year,
        "current_month": 1,
        "current_count": 0,
        "median_for_current_month": 0.0,
        "current_anomaly_pct": 0.0,
        "total_fires": 0,
        "total_modis": 0,
        "total_viirs": 0,
        "sensors_used": [],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }