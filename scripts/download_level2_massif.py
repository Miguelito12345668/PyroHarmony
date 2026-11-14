import earthaccess
from pathlib import Path
from datetime import date

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Coordonnées de la bounding box du Cameroun (Ouest, Sud, Est, Nord)
CAMEROON_BBOX = (8.5, 1.6, 16.2, 13.1)
OUTPUT_DIR = Path("./cache/level2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Plage d'années souhaitée
START_YEAR = 2000
END_YEAR = 2025

# ⚠️ IMPORTANT : Limite le nombre de granules par année pour les tests.
# Mets `None` pour tout télécharger (attention : volume énorme, plusieurs Go par an).
# Pour un test rapide, garde 10 ou 20.
MAX_GRANULES_PER_YEAR = 10 

# Produits à télécharger
# Note : MYD14 (Aqua) ne commence qu'en 2002. Le script gérera les années vides.
products = {
    "MOD14": "MODIS_Terra_Thermal_Anomalies_5-Min_L2",
    "MYD14": "MODIS_Aqua_Thermal_Anomalies_5-Min_L2",
    "VNP14IMG": "VIIRS_375m_Active_Fire_Product_5-Min_L2"
}

# ==========================================
# 2. AUTHENTIFICATION
# ==========================================
print("Authentification auprès de la NASA...")
earthaccess.login()

# ==========================================
# 3. TÉLÉCHARGEMENT ANNÉE PAR ANNÉE
# ==========================================
for year in range(START_YEAR, END_YEAR + 1):
    print(f"\n{'='*50}")
    print(f"TRAITEMENT DE L'ANNÉE {year}")
    print(f"{'='*50}")

    # Définition de la plage temporelle pour l'année en cours
    temporal_range = (f"{year}-01-01", f"{year}-12-31")

    for short_name, description in products.items():
        print(f"\n--- Recherche pour {short_name} ({description}) ---")

        # Recherche des granules
        try:
            # count=-1 récupère TOUS les granules. On applique notre limite si définie.
            results = earthaccess.search_data(
                short_name=short_name,
                bounding_box=CAMEROON_BBOX,
                temporal=temporal_range,
                count=MAX_GRANULES_PER_YEAR if MAX_GRANULES_PER_YEAR else -1
            )
        except Exception as e:
            print(f"Erreur lors de la recherche pour {short_name} en {year} : {e}")
            continue

        if not results:
            print(f"Aucun granule trouvé pour {short_name} en {year}.")
            continue

        print(f"{len(results)} granules trouvés. Téléchargement...")

        # Créer un sous-dossier par produit ET par année pour s'organiser
        product_dir = OUTPUT_DIR / short_name / str(year)
        product_dir.mkdir(parents=True, exist_ok=True)

        # Téléchargement
        try:
            # earthaccess.download gère le multithreading et ignore les fichiers déjà présents
            files = earthaccess.download(results, local_path=str(product_dir))
            print(f"✅ {len(files)} fichiers téléchargés pour {short_name} / {year}.")
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement de {short_name} / {year} : {e}")

print("\n🎉 Script de téléchargement massif terminé.")