from pathlib import Path

CONTENT = '''"""
Script d'harmonisation Level-2 pour l'année 2024.
CORRECTION : extraction de la date depuis le nom du fichier.
"""
import pandas as pd
import numpy as np
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from pyhdf.SD import SD, SDC
from netCDF4 import Dataset
from scipy.spatial import cKDTree

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "cache" / "level2_cameroun"
OUTPUT_FILE = BASE_DIR / "cache" / "cameroun_harmonized_2024.parquet"
BBOX = {'lat_min': 1.6, 'lat_max': 13.1, 'lon_min': 8.5, 'lon_max': 16.2}
TARGET_YEAR = "2024"
LIMIT_FILES = None

def extract_date_from_filename(filepath):
    match = re.search(r'\\.A(\\d{4})(\\d{3})\\.', filepath.name)
    if match:
        year = int(match.group(1))
        doy = int(match.group(2))
        try:
            dt = datetime(year, 1, 1) + timedelta(days=doy - 1)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, OverflowError):
            return None
    return None

def read_modis(filepath):
    try:
        hdf = SD(str(filepath), SDC.READ)
        lats = hdf.select('FP_latitude')[:]
        lons = hdf.select('FP_longitude')[:]
        frp = hdf.select('FP_power')[:]
        vza = hdf.select('FP_ViewZenAng')[:]
        hdf.end()
        date_str = extract_date_from_filename(filepath)
        if not date_str:
            return pd.DataFrame()
        mask = (lats >= BBOX['lat_min']) & (lats <= BBOX['lat_max']) & \\
               (lons >= BBOX['lon_min']) & (lons <= BBOX['lon_max']) & (frp > 0)
        return pd.DataFrame({
            'latitude': lats[mask], 'longitude': lons[mask],
            'frp': frp[mask], 'vza': vza[mask], 'date': date_str,
            'sensor': 'MODIS', 'matched': False, 'frp_corrigee': frp[mask]
        })
    except Exception:
        return pd.DataFrame()

def read_viirs(filepath):
    try:
        nc = Dataset(str(filepath), 'r')
        lats = nc.variables['FP_latitude'][:]
        lons = nc.variables['FP_longitude'][:]
        frp = nc.variables['FP_power'][:]
        vza = nc.variables['FP_ViewZenAng'][:]
        nc.close()
        date_str = extract_date_from_filename(filepath)
        if not date_str:
            return pd.DataFrame()
        mask = (lats >= BBOX['lat_min']) & (lats <= BBOX['lat_max']) & \\
               (lons >= BBOX['lon_min']) & (lons <= BBOX['lon_max']) & (frp > 0)
        return pd.DataFrame({
            'latitude': lats[mask], 'longitude': lons[mask],
            'frp': frp[mask], 'vza': vza[mask], 'date': date_str,
            'sensor': 'VIIRS', 'matched': False, 'frp_corrigee': frp[mask]
        })
    except Exception:
        return pd.DataFrame()

def load_all_data():
    print(f"Chargement des données Level-2 pour le Cameroun — ANNÉE {TARGET_YEAR}...")
    dfs_modis, dfs_viirs = [], []
    modis_files = [f for f in DATA_DIR.glob("MOD14/**/*.hdf") if TARGET_YEAR in f.name] + \\
                  [f for f in DATA_DIR.glob("MYD14/**/*.hdf") if TARGET_YEAR in f.name]
    viirs_files = [f for f in DATA_DIR.glob("VNP14IMG/**/*.nc") if TARGET_YEAR in f.name]
    print(f"Fichiers trouvés pour {TARGET_YEAR} :")
    print(f"  → MODIS : {len(modis_files)} fichiers")
    print(f"  → VIIRS : {len(viirs_files)} fichiers")
    if LIMIT_FILES:
        modis_files = modis_files[:LIMIT_FILES]
        viirs_files = viirs_files[:LIMIT_FILES]
    print(f"\\nLecture de {len(modis_files)} fichiers MODIS...")
    for i, f in enumerate(modis_files):
        if i % 100 == 0: print(f"  -> MODIS: {i}/{len(modis_files)}")
        df = read_modis(f)
        if not df.empty: dfs_modis.append(df)
    print(f"\\nLecture de {len(viirs_files)} fichiers VIIRS...")
    for i, f in enumerate(viirs_files):
        if i % 100 == 0: print(f"  -> VIIRS: {i}/{len(viirs_files)}")
        df = read_viirs(f)
        if not df.empty: dfs_viirs.append(df)
    df_m = pd.concat(dfs_modis, ignore_index=True) if dfs_modis else pd.DataFrame()
    df_v = pd.concat(dfs_viirs, ignore_index=True) if dfs_viirs else pd.DataFrame()
    print(f"\\nTotal MODIS {TARGET_YEAR} (Cameroun) : {len(df_m)} feux")
    print(f"Total VIIRS {TARGET_YEAR} (Cameroun) : {len(df_v)} feux")
    if not df_m.empty:
        months_m = pd.to_datetime(df_m['date']).dt.month.value_counts().sort_index()
        print(f"\\nRépartition mensuelle MODIS : {dict(months_m)}")
        print(f"Jours distincts MODIS : {df_m['date'].nunique()}")
    if not df_v.empty:
        months_v = pd.to_datetime(df_v['date']).dt.month.value_counts().sort_index()
        print(f"Répartition mensuelle VIIRS : {dict(months_v)}")
        print(f"Jours distincts VIIRS : {df_v['date'].nunique()}")
    return df_m, df_v

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

def match_and_correct(df_m, df_v):
    if df_m.empty or df_v.empty:
        return pd.concat([df_m, df_v], ignore_index=True) if not df_m.empty or not df_v.empty else pd.DataFrame()
    print("\\nAppariement spatial (rayon 1 km)...")
    tree = cKDTree(df_v[['latitude', 'longitude']].values)
    indices = tree.query_ball_point(df_m[['latitude', 'longitude']].values, r=0.01)
    matched_modis_indices = []
    matched_viirs_indices = set()
    for i, neighbors in enumerate(indices):
        if not neighbors: continue
        m_row = df_m.iloc[i]
        for j in neighbors:
            v_row = df_v.iloc[j]
            if haversine(m_row['latitude'], m_row['longitude'], v_row['latitude'], v_row['longitude']) <= 1.0:
                vza_factor = 1.0 + (m_row['vza'] / 60.0) * 0.3
                df_m.loc[i, 'frp_corrigee'] = m_row['frp'] * vza_factor
                df_m.loc[i, 'matched'] = True
                matched_modis_indices.append(i)
                matched_viirs_indices.add(j)
                break
    print(f"Feux appariés trouvés : {len(matched_modis_indices)}")
    df_m_matched = df_m.iloc[matched_modis_indices].copy()
    df_m_matched['sensor'] = 'MODIS (Corrigé)'
    df_m_unmatched = df_m.drop(index=matched_modis_indices).copy()
    df_v_unmatched = df_v.drop(index=list(matched_viirs_indices)).copy()
    return pd.concat([df_m_matched, df_m_unmatched, df_v_unmatched], ignore_index=True)

if __name__ == "__main__":
    start_time = time.time()
    df_m, df_v = load_all_data()
    if not df_m.empty or not df_v.empty:
        final_df = match_and_correct(df_m, df_v)
        print("\\n--- RÉSULTAT FINAL (2024) ---")
        print(f"Total feux harmonisés : {len(final_df)}")
        print(f"\\nAperçu (5 premiers feux) :")
        print(final_df[['date', 'sensor', 'frp', 'frp_corrigee']].head())
        final_df['date_str'] = final_df['date'].astype(str)
        years_in_data = sorted(final_df['date_str'].str[:4].unique())
        months_in_data = sorted(pd.to_datetime(final_df['date']).dt.month.unique())
        days_count = final_df['date_str'].nunique()
        print(f"\\n=== VÉRIFICATIONS ===")
        print(f"Années présentes : {years_in_data}")
        print(f"Mois présents : {months_in_data}")
        print(f"Nombre de jours distincts : {days_count}")
        if len(months_in_data) == 12 and days_count > 300:
            print("✅ BON : les dates sont correctement réparties sur l'année !")
        else:
            print("⚠️ ATTENTION : les dates semblent incomplètes.")
        print(f"\\nSauvegarde vers {OUTPUT_FILE}...")
        final_df.to_parquet(OUTPUT_FILE)
        elapsed = time.time() - start_time
        print(f"\\n✅ Fichier Parquet 2024 généré en {elapsed/60:.1f} minutes !")
    else:
        print("Aucune donnée trouvée.")
'''

# ⚠️ CORRECTION : le script est dans scripts/, donc on cible directement scripts/process_level2_2024.py
# AVANT : path = Path(__file__).parent / "scripts" / "process_level2_2024.py"  ← bug (scripts/scripts)
# APRÈS : path = Path(__file__).parent / "process_level2_2024.py"               ← correct
path = Path(__file__).parent / "process_level2_2024.py"

path.write_text(CONTENT, encoding="utf-8")
print(f"✅ Fichier créé : {path}")
print(f"   Taille : {len(CONTENT)} caractères")

# Vérification
if "extract_date_from_filename" in path.read_text(encoding="utf-8"):
    print("✅ Vérification OK : la fonction extract_date_from_filename est présente")
else:
    print("❌ ERREUR : la fonction n'est pas dans le fichier")