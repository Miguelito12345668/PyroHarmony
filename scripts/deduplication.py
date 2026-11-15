"""
Déduplique les Parquet 2024 et 2025-2026 pour qu'ils soient comparables aux CSV NASA.
Règle : 1 événement = tous les feux dans la même cellule géographique (~1 km) le même jour.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.spatial import cKDTree

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache"

def deduplicate(df, dist_km=1.0):
    """
    Déduplique les détections par (date + proximité spatiale).
    Retourne un DataFrame avec un seul représentant par événement.
    """
    if df.empty:
        return df
    
    df = df.copy()
    df['date_str'] = df['date'].astype(str).str[:10]
    
    unique_events = []
    
    # Traiter jour par jour
    for date, day_df in df.groupby('date_str'):
        if day_df.empty:
            continue
        
        coords = day_df[['latitude', 'longitude']].values
        tree = cKDTree(coords)
        
        used = np.zeros(len(day_df), dtype=bool)
        
        for i in range(len(day_df)):
            if used[i]:
                continue
            
            # Trouver tous les voisins à moins de dist_km
            # r en degrés : 1 km ≈ 0.009 degré
            r_deg = dist_km / 111.0
            neighbors = tree.query_ball_point(coords[i], r=r_deg)
            
            # Marquer comme utilisés
            group = day_df.iloc[neighbors]
            used[neighbors] = True
            
            # Garder le feu avec la FRP corrigée la plus élevée (le plus significatif)
            best_row = group.loc[group['frp_corrigee'].idxmax()]
            unique_events.append(best_row)
    
    return pd.DataFrame(unique_events).reset_index(drop=True)


def process_file(input_path, output_path):
    if not input_path.exists():
        print(f"⚠️  Fichier non trouvé : {input_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"Traitement : {input_path.name}")
    print(f"{'='*60}")
    
    df = pd.read_parquet(input_path)
    print(f"Feux avant déduplication : {len(df):,}")
    
    # Aperçu des années
    years_before = sorted(df['date'].astype(str).str[:4].unique())
    print(f"Années : {years_before}")
    
    df_dedup = deduplicate(df, dist_km=1.0)
    print(f"Feux après déduplication : {len(df_dedup):,}")
    print(f"Réduction : {(1 - len(df_dedup)/len(df)) * 100:.1f}%")
    
    df_dedup.to_parquet(output_path)
    print(f"✅ Sauvegardé : {output_path.name}")


if __name__ == "__main__":
    # 1. Dédupliquer 2024
    process_file(
        CACHE_DIR / "cameroun_harmonized_2024.parquet",
        CACHE_DIR / "cameroun_harmonized_2024_dedup.parquet"
    )
    
    # 2. Dédupliquer 2025-2026
    process_file(
        CACHE_DIR / "cameroun_harmonized.parquet",
        CACHE_DIR / "cameroun_harmonized_dedup.parquet"
    )
    
    print("\n🎉 Déduplication terminée !")