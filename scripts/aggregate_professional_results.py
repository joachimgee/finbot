#!/usr/bin/env python3
"""
Aggregation Script - Professional Analysis Regional Results
===========================================================

Fusionne les résultats régionaux (US / EU / ASIA / AMERICAS / FULL optionnel) en un
classement global consolidé.

Logic:
 1. Charger tous les CSV trouvés correspondant aux patterns:
      professional_analysis_*.csv
 2. Ajouter colonne 'region' dérivée du nom de fichier
 3. Normaliser scores (min-max sur composite_score global)
 4. Calculer rang global et rang régional
 5. Dédupliquer symboles (garder meilleur score composite)
 6. Produire fichier final: professional_analysis_aggregated.csv

Usage:
    python scripts/aggregate_professional_results.py --output aggregated.csv

Sortie colonnes:
    symbol,region,composite_score,normalized_score,num_factors_computed,confidence,
    alpha_score,ml_score,technical_score,fundamental_score,sentiment_score,global_rank,regional_rank

"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import List
import pandas as pd

REGION_MAP = {
    'us': 'United States',
    'eu': 'Europe',
    'asia': 'Asia',
    'americas': 'Americas',
    'full': 'Global'
}

def infer_region(filename: str) -> str:
    name = filename.lower()
    for key in REGION_MAP:
        if key in name:
            return REGION_MAP[key]
    return 'Unknown'

def load_csv_files(paths: List[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if 'symbol' not in df.columns or 'composite_score' not in df.columns:
                continue
            df['region'] = infer_region(p.name)
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # Rang régional
    df['regional_rank'] = df.groupby('region')['composite_score'].rank(ascending=False, method='first')
    # Dedup symbol (garder meilleur score)
    df = df.sort_values('composite_score', ascending=False).drop_duplicates('symbol')
    # Normalisation
    min_score = df['composite_score'].min()
    max_score = df['composite_score'].max()
    span = max(max_score - min_score, 1e-9)
    df['normalized_score'] = (df['composite_score'] - min_score) / span
    # Rang global
    df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)
    df['global_rank'] = df.index + 1
    # Réordonner colonnes
    cols = [
        'symbol','region','composite_score','normalized_score','num_factors_computed','confidence',
        'alpha_score','ml_score','technical_score','fundamental_score','sentiment_score','global_rank','regional_rank'
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def main():
    parser = argparse.ArgumentParser(description='Aggregate regional professional analysis results')
    parser.add_argument('--directory', type=str, default='.', help='Directory containing CSV result files')
    parser.add_argument('--output', type=str, default='professional_analysis_aggregated.csv', help='Output aggregated CSV file')
    args = parser.parse_args()

    root = Path(args.directory)
    patterns = [
        'professional_analysis_us.csv',
        'professional_analysis_eu.csv',
        'professional_analysis_asia.csv',
        'professional_analysis_americas.csv',
        'professional_analysis_full_30k.csv'
    ]
    files = [root / p for p in patterns if (root / p).exists()]
    # Fallback: glob any matching
    if not files:
        files = list(root.glob('professional_analysis_*.csv'))

    print(f"Found {len(files)} files for aggregation")
    for f in files:
        print(f"  - {f.name}")

    df = load_csv_files(files)
    if df.empty:
        print("No valid data files found. Exit.")
        return

    aggregated = aggregate(df)
    aggregated.to_csv(args.output, index=False)
    print(f"Aggregated file written: {args.output} ({len(aggregated)} rows)")
    print("Top 10 (symbol, score, region):")
    print(aggregated[['symbol','composite_score','region']].head(10).to_string(index=False))

if __name__ == '__main__':
    main()
