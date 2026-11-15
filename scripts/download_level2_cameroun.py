import earthaccess
from pathlib import Path
import sys

# ==========================================
# 1. CONFIGURATION SPÉCIFIQUE CAMEROUN
# ==========================================
# BBOX du Cameroun (Ouest, Sud, Est, Nord)
CAMEROON_BBOX = (8.5, 1.6, 16.2, 13.1)

# Dossier de destination
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "cache" / "level2_cameroun"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Période : 2025 jusqu'au 2 novembre 2026 (fin de Suomi-NPP)
START_DATE = "2025-01-01"
END_DATE = "2026-11-02"

# Produits NASA
products = {
    "MOD14": "MODIS_Terra_Thermal_Anomalies_5-Min_L2",
    "MYD14": "MODIS_Aqua_Thermal_Anomalies_5-Min_L2",
    "VNP14IMG": "VIIRS_375m_Active_Fire_Product_5-Min_L2"
}

# ==========================================
# 2. AUTHENTIFICATION
# ==========================================
print("Authentification auprès de la NASA...")
try:
    earthaccess.login()
except Exception as e:
    print(f"Erreur d'authentification : {e}")
    sys.exit(1)

# ==========================================
# 3. TÉLÉCHARGEMENT SANS LIMITE
# ==========================================
print(f"\nDébut du téléchargement pour le CAMEROUN...")
print(f"Période : Du {START_DATE} au {END_DATE}")
print(f"Destination : {OUTPUT_DIR}")

for year in [2025, 2026]:
    print(f"\n{'='*50}")
    print(f"TRAITEMENT DE L'ANNÉE {year}")
    print(f"{'='*50}")

    start_of_year = f"{year}-01-01"
    end_of_year = f"{year}-12-31"
    
    # Ajustement pour ne pas dépasser les bornes
    if start_of_year < START_DATE:
        start_of_year = START_DATE
    if end_of_year > END_DATE:
        end_of_year = END_DATE
        
    temporal_range = (start_of_year, end_of_year)
    print(f"Recherche pour la période : {temporal_range[0]} à {temporal_range[1]}")

    for short_name, description in products.items():
        print(f"\n--- Recherche pour {short_name} ---")

        try:
            # count=-1 signifie "TOUT TÉLÉCHARGER"
            results = earthaccess.search_data(
                short_name=short_name,
                bounding_box=CAMEROON_BBOX,
                temporal=temporal_range,
                count=-1 
            )
        except Exception as e:
            print(f"Erreur API pour {short_name} : {e}")
            continue

        if not results:
            print(f"Aucun granule trouvé pour {short_name} sur cette période.")
            continue

        print(f"{len(results)} granules trouvés. Téléchargement en cours...")

        # Dossier : cache/level2_cameroun/MOD14/2025/
        product_dir = OUTPUT_DIR / short_name / str(year)
        product_dir.mkdir(parents=True, exist_ok=True)

        try:
            files = earthaccess.download(results, local_path=str(product_dir))
            print(f"✅ {len(files)} fichiers téléchargés.")
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement : {e}")

print("\n🎉 Script de téléchargement Cameroun terminé.")