import earthaccess
from pathlib import Path
import sys

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Bounding Box pour l'Afrique Centrale
# Ouest, Sud, Est, Nord
CENTRAL_AFRICA_BBOX = (8.0, -18.0, 32.0, 24.0)

# Résolution robuste du chemin vers le dossier cache/level2
# (remonte de scripts/ vers la racine du projet)
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "cache" / "level2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Plage d'années
START_YEAR = 2000
END_YEAR = 2025

# ⚠️ LIMITE DE SÉCURITÉ
# Mets 10 pour tester. Passe à 50 ou None (tout) quand tu es prêt.
MAX_GRANULES_PER_YEAR = 10 

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
# 3. TÉLÉCHARGEMENT
# ==========================================
print(f"\nDébut du téléchargement pour l'Afrique Centrale (BBOX: {CENTRAL_AFRICA_BBOX})")
print(f"Destination : {OUTPUT_DIR}")

for year in range(START_YEAR, END_YEAR + 1):
    print(f"\n{'='*50}")
    print(f"TRAITEMENT DE L'ANNÉE {year}")
    print(f"{'='*50}")

    temporal_range = (f"{year}-01-01", f"{year}-12-31")

    for short_name, description in products.items():
        print(f"\n--- Recherche pour {short_name} ---")

        try:
            results = earthaccess.search_data(
                short_name=short_name,
                bounding_box=CENTRAL_AFRICA_BBOX,
                temporal=temporal_range,
                count=MAX_GRANULES_PER_YEAR if MAX_GRANULES_PER_YEAR else -1
            )
        except Exception as e:
            print(f"Erreur API pour {short_name} en {year} : {e}")
            continue

        if not results:
            print(f"Aucun granule trouvé pour {short_name} en {year}.")
            continue

        print(f"{len(results)} granules trouvés. Téléchargement...")

        # Dossier de destination : cache/level2/MOD14/2023/
        product_dir = OUTPUT_DIR / short_name / str(year)
        product_dir.mkdir(parents=True, exist_ok=True)

        try:
            files = earthaccess.download(results, local_path=str(product_dir))
            print(f"✅ {len(files)} fichiers téléchargés.")
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement : {e}")

print("\n🎉 Script de téléchargement terminé.")