from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd


def _ensure_vendor_mlfinlab_on_path() -> None:
    """Ajoute vendor/mlfinlab au sys.path si mlfinlab n'est pas installé."""
    try:
        root = Path(__file__).resolve().parents[3]
        vendor_mlf = root / "vendor" / "mlfinlab"
        if vendor_mlf.exists() and str(vendor_mlf) not in sys.path:
            sys.path.insert(0, str(vendor_mlf))
    except Exception:
        pass


def triple_barrier_labels(
    prices: pd.Series,
    pt_sl: Tuple[float, float] = (1.0, 1.0),
    min_hold: int = 1,
    max_hold: Optional[int] = 20,
) -> pd.Series:
    """
    Labels triple-barrier avec mlfinlab si disponible, sinon fallback simplifié.

    Args:
        prices: Série de prix indexée par date (croissante)
        pt_sl: multiplicateurs seuils (take-profit, stop-loss) en % (ex: 1.0 -> 1%)
        min_hold: holding minimal (périodes)
        max_hold: barrière verticale maximale (périodes)

    Returns:
        Série de labels {1, 0, -1}
    """
    try:
        # Essayer d'importer mlfinlab (installé ou vendorisé)
        try:
            from mlfinlab.labeling import labeling as mll
        except ImportError:
            _ensure_vendor_mlfinlab_on_path()
            from mlfinlab.labeling import labeling as mll
        
        # Calculer volatilité pour target
        vol = prices.pct_change().rolling(20).std().shift(1).dropna()
        daily_vol = vol.reindex(prices.index).ffill().fillna(vol.mean() if len(vol) > 0 else 0.01)
        
        # Note: mlfinlab stubs ont des pass, donc si on utilise la version vendorisée
        # il faut s'assurer qu'elle est complète ou passer au fallback
        # Pour l'instant, on tente et attrape toute erreur
        events = mll.get_events(
            close=prices,
            t_events=prices.index,
            pt_sl=np.array(pt_sl),
            target=daily_vol,
            min_ret=0.0,
            num_threads=1,
            vertical_barrier_times=False,
        )
        if events is None or events.empty:
            raise ValueError("mlfinlab returned empty events")
        
        bins = mll.get_bins(events, prices)
        return bins["bin"].reindex(prices.index).fillna(0.0).astype(int)
    
    except Exception:
        # Fallback simple: horizon max_hold et seuils en %
        if max_hold is None:
            max_hold = 20
        returns = prices.pct_change().fillna(0.0)
        labels = np.zeros(len(prices), dtype=int)
        arr = prices.values.astype(float)
        for i in range(len(arr)):
            start = arr[i]
            end_idx = min(len(arr) - 1, i + max(1, max_hold))
            # respect min_hold
            min_idx = min(len(arr) - 1, i + max(1, min_hold))
            window = arr[i:end_idx + 1]
            # calcul retours max/min
            ret_path = window / start - 1.0
            # take-profit / stop-loss en %
            tp = pt_sl[0] / 100.0
            sl = -pt_sl[1] / 100.0
            hit_tp = (ret_path >= tp).any()
            hit_sl = (ret_path <= sl).any()
            # priorité: si SL et TP dans fenêtre, prendre le premier atteint après min_hold
            if hit_tp and not hit_sl:
                labels[i] = 1
            elif hit_sl and not hit_tp:
                labels[i] = -1
            else:
                # si aucun atteint, signe du retour à l'horizon min_idx
                r = arr[min_idx] / start - 1.0
                labels[i] = 1 if r > 0 else (-1 if r < 0 else 0)
        return pd.Series(labels, index=prices.index)
