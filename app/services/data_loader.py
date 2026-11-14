import asyncio
import logging
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

    # Timeout passé à 5 minutes (300s) pour les gros fichiers VIIRS
    async with httpx.AsyncClient(timeout=300) as client:
        for product_name in product_names:
            product = _resolve_archive_product(product_name)
            for year in years:
                rows = None
                
                # --- RETRY SYSTEM (3 tentatives) ---
                for attempt in range(3):
                    try:
                        # Ajout de directory=settings.cache_dir pour forcer le cache local
                        rows = await fetch_archive(
                            client, product, year, country, directory=settings.cache_dir
                        )
                        break  # Succès, on sort de la boucle
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"Échec définitif {product_name}/{year}: {e}")
                        else:
                            logger.warning(f"Retry {attempt+1}/3 pour {product_name}/{year} (coupure réseau)...")
                            await asyncio.sleep(2)  # Attendre 2s avant de réessayer
                # -----------------------------------

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