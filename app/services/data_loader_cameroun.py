"""
Data loader hybride : CSV NASA (2000-2023) + Parquet dédupliqué (2024-2026).
"""
import asyncio
import logging
from typing import Any
import httpx
import pandas as pd

from app.core.settings import settings
from app.core import cache

logger = logging.getLogger(__name__)

try:
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


def _filter_by_bbox(rows: list[Any], bbox: list[float] | None) -> list[Any]:
    if not bbox or len(bbox) != 4:
        return rows
    lon_min, lat_min, lon_max, lat_max = bbox
    filtered = []
    for r in rows:
        lat = getattr(r, "latitude", None)
        lon = getattr(r, "longitude", None)
        if lat is None or lon is None:
            continue
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            filtered.append(r)
    return filtered


async def fetch_archive_years(zone: dict, years: list[int]) -> list[Any]:
    if not FIRMS_CLIENT_AVAILABLE:
        raise RuntimeError("firms-client n'est pas installé")
    
    country = zone.get("archive_country_name")
    if not country:
        raise ValueError("Zone sans nom de pays d'archive")

    product_names = zone.get("products_archive", ["MODIS", "VIIRS_SNPP"])
    all_rows: list[Any] = []

    async with httpx.AsyncClient(timeout=300) as client:
        for product_name in product_names:
            product = _resolve_archive_product(product_name)
            for year in years:
                rows = None
                for attempt in range(3):
                    try:
                        rows = await fetch_archive(
                            client, product, year, country,
                            directory=settings.cache_dir
                        )
                        break
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"Échec définitif {product_name}/{year}: {e}")
                        else:
                            await asyncio.sleep(2)

                if not rows:
                    continue

                try:
                    filtered = select(rows, vegetation_only=False, min_confidence="nominal")
                except Exception:
                    filtered = rows

                all_rows.extend(filtered)
                logger.info(f"{product_name}/{year}/{country}: {len(filtered)} feux (CSV)")

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
                rows = await fetch_area(
                    client, settings.firms_map_key, product, bbox, days=days
                )
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


class CsvRow:
    def __init__(self, base, weight=1.0):
        self.latitude = base.latitude
        self.longitude = base.longitude
        self.acq_date = str(getattr(base, 'acq_date', ''))
        self.instrument = getattr(base, 'instrument', 'MODIS')
        self.frp_mw = getattr(base, 'frp_mw', 0.0)
        self.weight = weight


class ParquetRow:
    def __init__(self, row_dict):
        self.latitude = row_dict['latitude']
        self.longitude = row_dict['longitude']
        self.acq_date = str(row_dict['date'])
        self.instrument = row_dict['sensor']
        self.frp_mw = row_dict['frp_corrigee']
        self.weight = 1.0


async def get_cached_archive(zone_id: str, zone: dict, years: list[int]):
    key = f"archive_v4:{zone_id}:{min(years)}:{max(years)}"
    cached = cache.get(key, settings.cache_ttl_seconds)
    if cached is not None:
        logger.info(f"Cache HIT {key}")
        return cached

    bbox = zone.get("bbox")
    all_rows = []

    # 1. CSV NASA 2000-2023
    csv_years = [y for y in years if y <= 2023]
    if csv_years:
        csv_rows = await fetch_archive_years(zone, csv_years)
        if bbox:
            csv_rows = _filter_by_bbox(csv_rows, bbox)
        for r in csv_rows:
            all_rows.append(CsvRow(r, weight=1.0))
        logger.info(f"CSV 2000-2023 : {len(csv_rows)} feux")

    # 2. Parquet 2024 DÉDUPLIQUÉ
    p2024 = settings.cache_dir / "cameroun_harmonized_2024_dedup.parquet"
    if p2024.exists() and any(y == 2024 for y in years):
        df24 = pd.read_parquet(p2024)
        if bbox:
            lon_min, lat_min, lon_max, lat_max = bbox
            df24 = df24[
                (df24['latitude'] >= lat_min) & (df24['latitude'] <= lat_max) &
                (df24['longitude'] >= lon_min) & (df24['longitude'] <= lon_max)
            ]
        for _, row in df24.iterrows():
            all_rows.append(ParquetRow(row))
        logger.info(f"Parquet 2024 (dédupliqué) : {len(df24)} feux")

    # 3. Parquet 2025-2026 DÉDUPLIQUÉ
    p_recent = settings.cache_dir / "cameroun_harmonized_dedup.parquet"
    if p_recent.exists() and any(y >= 2025 for y in years):
        df_recent = pd.read_parquet(p_recent)
        if bbox:
            lon_min, lat_min, lon_max, lat_max = bbox
            df_recent = df_recent[
                (df_recent['latitude'] >= lat_min) & (df_recent['latitude'] <= lat_max) &
                (df_recent['longitude'] >= lon_min) & (df_recent['longitude'] <= lon_max)
            ]
        for _, row in df_recent.iterrows():
            all_rows.append(ParquetRow(row))
        logger.info(f"Parquet 2025-2026 (dédupliqué) : {len(df_recent)} feux")

    logger.info(f"Total chargé pour {zone_id} : {len(all_rows)} feux")

    cache.set(key, (all_rows, 1.0))
    return all_rows, 1.0