import pandas as pd
import numpy as np
from pathlib import Path
from pyhdf.SD import SD, SDC
from netCDF4 import Dataset
from scipy.spatial import cKDTree

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "cache" / "level2_cameroun"
OUTPUT_FILE = BASE_DIR / "cache" / "cameroun_harmonized.parquet"

# BBOX du Cameroun
BBOX = {'lat_min': 1.6, 'lat_max': 13.1, 'lon_min': 8.5, 'lon_max': 16.2}

# ⚠️ MODE TRAITEMENT COMPLET : None pour tout traiter
LIMIT_FILES = None 

# ==========================================
# ÉTAPE 1 : EXTRACTION DES DONNÉES
# ==========================================

def read_modis(filepath):
    try:
        hdf = SD(str(filepath), SDC.READ)
        lats = hdf.select('FP_latitude')[:]
        lons = hdf.select('FP_longitude')[:]
        frp = hdf.select('FP_power')[:]
        vza = hdf.select('FP_ViewZenAng')[:]
        
        attrs = hdf.attributes()
        date_str = attrs.get('START_DATE', '2025-01-01')
        hdf.end()
        
        mask = (lats >= BBOX['lat_min']) & (lats <= BBOX['lat_max']) & \
               (lons >= BBOX['lon_min']) & (lons <= BBOX['lon_max']) & \
               (frp > 0)
               
        # CORRECTION : Initialisation de 'matched' et 'frp_corrigee' directement ici
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
        
        date_str = getattr(nc, 'START_DATE', '2025-01-01')
        nc.close()
        
        mask = (lats >= BBOX['lat_min']) & (lats <= BBOX['lat_max']) & \
               (lons >= BBOX['lon_min']) & (lons <= BBOX['lon_max']) & \
               (frp > 0)
               
        # CORRECTION : Initialisation de 'matched' et 'frp_corrigee' directement ici
        return pd.DataFrame({
            'latitude': lats[mask], 'longitude': lons[mask],
            'frp': frp[mask], 'vza': vza[mask], 'date': date_str, 
            'sensor': 'VIIRS', 'matched': False, 'frp_corrigee': frp[mask]
        })
    except Exception:
        return pd.DataFrame()

def load_all_data():
    print("Chargement des données Level-2 pour le Cameroun...")
    dfs_modis, dfs_viirs = [], []
    
    modis_files = list(DATA_DIR.glob("MOD14/**/*.hdf")) + list(DATA_DIR.glob("MYD14/**/*.hdf"))
    viirs_files = list(DATA_DIR.glob("VNP14IMG/**/*.nc"))
    
    if LIMIT_FILES:
        modis_files = modis_files[:LIMIT_FILES]
        viirs_files = viirs_files[:LIMIT_FILES]
        
    print(f"Lecture de {len(modis_files)} fichiers MODIS...")
    for i, f in enumerate(modis_files):
        if i % 100 == 0: print(f"  -> MODIS: {i}/{len(modis_files)}")
        df = read_modis(f)
        if not df.empty: dfs_modis.append(df)
        
    print(f"Lecture de {len(viirs_files)} fichiers VIIRS...")
    for i, f in enumerate(viirs_files):
        if i % 100 == 0: print(f"  -> VIIRS: {i}/{len(viirs_files)}")
        df = read_viirs(f)
        if not df.empty: dfs_viirs.append(df)
        
    df_m = pd.concat(dfs_modis, ignore_index=True) if dfs_modis else pd.DataFrame()
    df_v = pd.concat(dfs_viirs, ignore_index=True) if dfs_viirs else pd.DataFrame()
    
    print(f"\nTotal MODIS (Cameroun) : {len(df_m)} feux")
    print(f"Total VIIRS (Cameroun) : {len(df_v)} feux")
    return df_m, df_v

# ==========================================
# ÉTAPE 2 : APPARIEMENT ET CORRECTION
# ==========================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

def match_and_correct(df_m, df_v):
    if df_m.empty or df_v.empty:
        return pd.concat([df_m, df_v], ignore_index=True) if not df_m.empty or not df_v.empty else pd.DataFrame()

    print("\nAppariement spatial (rayon 1 km)...")
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
                # CORRECTION DU VZA : Plus l'angle est grand, plus on augmente la FRP
                vza_factor = 1.0 + (m_row['vza'] / 60.0) * 0.3
                
                # CORRECTION : Utilisation de .loc pour éviter le Pandas4Warning
                df_m.loc[i, 'frp_corrigee'] = m_row['frp'] * vza_factor
                df_m.loc[i, 'matched'] = True
                
                matched_modis_indices.append(i)
                matched_viirs_indices.add(j)
                break 

    print(f"Feux appariés trouvés : {len(matched_modis_indices)}")
    
    # --- FUSION FINALE ---
    df_m_matched = df_m.iloc[matched_modis_indices].copy()
    df_m_matched['sensor'] = 'MODIS (Corrigé)'
    
    df_m_unmatched = df_m.drop(index=matched_modis_indices).copy()
    
    df_v_unmatched = df_v.drop(index=list(matched_viirs_indices)).copy()
    
    final_df = pd.concat([df_m_matched, df_m_unmatched, df_v_unmatched], ignore_index=True)
    return final_df

# ==========================================
# EXÉCUTION
# ==========================================
if __name__ == "__main__":
    df_m, df_v = load_all_data()
    
    if not df_m.empty or not df_v.empty:
        final_df = match_and_correct(df_m, df_v)
        print("\n--- RÉSULTAT FINAL ---")
        print(f"Total feux harmonisés : {len(final_df)}")
        print(final_df[['date', 'sensor', 'frp', 'frp_corrigee']].head())
        
        print(f"\nSauvegarde vers {OUTPUT_FILE}...")
        final_df.to_parquet(OUTPUT_FILE)
        print("✅ Fichier Parquet généré avec succès !")
    else:
        print("Aucune donnée trouvée. Vérifie les chemins et les variables.")