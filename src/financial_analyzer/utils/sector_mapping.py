from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def load_sector_mapping(path_or_json: str) -> Dict[str, str]:
    """
    Charge un mapping secteurs depuis un JSON inline ou un fichier CSV/JSON.

    Formats supportés:
    - JSON inline: '{"AAPL":"Technology", "MSFT":"Technology"}'
    - Fichier JSON: {"AAPL":"Technology", ...}
    - Fichier CSV: colonnes au choix parmi [ticker,symbol] et [sector,industry]

    Returns:
        Dict[str, str] mapping ticker -> secteur
    """
    # 1) Essayer JSON inline
    s = path_or_json.strip()
    if s.startswith("{") and s.endswith("}"):
        data = json.loads(s)
        return {str(k).strip(): str(v).strip() for k, v in data.items() if isinstance(v, str)}

    # 2) Charger depuis fichier
    p = Path(path_or_json)
    if not p.exists():
        raise FileNotFoundError(f"Sector map not found: {p}")

    if p.suffix.lower() in {".json"}:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON mapping: expected object")
        return {str(k).strip(): str(v).strip() for k, v in data.items() if isinstance(v, str)}

    # CSV
    df = pd.read_csv(p)
    cols = {c.lower(): c for c in df.columns}
    tcol = cols.get("ticker") or cols.get("symbol")
    scol = cols.get("sector") or cols.get("industry")
    if not tcol or not scol:
        raise ValueError("CSV must contain 'ticker'/'symbol' and 'sector'/'industry' columns")
    out = {}
    for _, row in df.iterrows():
        tk = str(row[tcol]).strip()
        sc = str(row[scol]).strip()
        if tk and sc and sc.lower() != "nan":
            out[tk] = sc
    return out


def save_sector_mapping(mapping: Dict[str, str], path: str) -> None:
    """Sauvegarde un mapping secteurs en JSON pretty."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
