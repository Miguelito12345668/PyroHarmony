import asyncio, sys
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
    print(f"\n{len(rows)} feux récupérés")
    if rows:
        r0 = rows[0]
        print(f"\nAttributs Hotspot: {[a for a in dir(r0) if not a.startswith('_')][:15]}")
        print(f"Premier (normalisé): {to_dict(r0, 'test')}")
        r = build_calendar(rows, "cameroun", 2023)
        print(f"\nTotal: {r['total_fires']}")
        print(f"Capteurs: {r['sensors_used']}")
        print(f"Années: {r['years']}")
        print(f"Médiane janv-déc: {[round(x, 1) for x in r['median_by_month']]}")
        print("\nPIPELINE VALIDÉ")
    else:
        print("AUCUNE DONNÉE")


if __name__ == "__main__":
    asyncio.run(main())
