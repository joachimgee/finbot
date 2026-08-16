"""Meta-labeling (López de Prado, *Advances in Financial ML* ch. 3) — filtrer/dimensionner
les paris du signal primaire sans en changer la direction.

Le signal **primaire** (momentum 12-1, cross-section) décide la **direction** :
long le meilleur quantile, short le pire. Un modèle **secondaire** (régression
logistique) apprend, sur des features connues à la date de décision, la probabilité
qu'un pari du primaire **gagne** (rendement forward *dans le sens du pari* > 0). On
s'en sert pour :

* **filtrer** — ne garder que les paris dont ``P(gain) ≥ seuil`` ;
* **dimensionner** — pondérer chaque pari par ``P(gain)``.

Ce n'est **pas** un nouveau signal directionnel : le méta-modèle ne peut que
*réduire* ou *ré-échelonner* les paris que le primaire a déjà choisis (précision ↑,
rappel ↓). Discipline **anti-look-ahead** : les labels utilisent des rendements
forward ; à chaque date de décision, l'entraînement n'utilise que des échantillons
**passés dont l'horizon de label est clos** (purge + embargo). Features motivées
*ex-ante* (pas de p-hacking) : conviction momentum, momentum court, low-vol (Barroso :
la vol prédit les krachs de momentum), reversal court, lottery.

Pur/testable : ne trade rien. L'évaluation (raw vs méta) passe par les mêmes coûts
calibrés que le portail ; le verdict reste soumis au portail (IC/Sharpe net + DSR).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["MetaResult", "META_FEATURES", "build_meta_samples", "walk_forward_meta"]

#: Features méta par défaut (clés de ``compute_classic_factors``), motivées ex-ante.
META_FEATURES = ("momentum_12_1", "momentum_6_1", "low_vol", "reversal_5", "max_lottery")


@dataclass
class MetaResult:
    """Comparaison raw vs méta-labeling (filtre / sizing), coûts inclus."""

    n_samples: int
    base_win_rate: float
    oos_auc: float
    raw_net_sharpe: float
    meta_filter_net_sharpe: float
    meta_size_net_sharpe: float
    raw_turnover: float
    meta_filter_turnover: float
    meta_size_turnover: float
    raw_avg_names: float
    meta_filter_avg_names: float

    def summary(self) -> str:
        return (
            f"raw Sharpe net {self.raw_net_sharpe:+.2f} (turnover {self.raw_turnover:.2f}, "
            f"{self.raw_avg_names:.0f} noms) | méta-filtre {self.meta_filter_net_sharpe:+.2f} "
            f"({self.meta_filter_turnover:.2f}, {self.meta_filter_avg_names:.0f} noms) | "
            f"méta-sizing {self.meta_size_net_sharpe:+.2f} | "
            f"AUC OOS {self.oos_auc:.3f} (base {self.base_win_rate:.0%})"
        )


def _sharpe(r: pd.Series, ppy: int = 252) -> float:
    r = pd.Series(r).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(ppy)) if len(r) > 1 and sd > 0 else 0.0


def build_meta_samples(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    *,
    quantile: float = 0.2,
    horizon: int = 10,
    feature_names: tuple[str, ...] = META_FEATURES,
) -> pd.DataFrame:
    """Table d'échantillons méta : une ligne par (date, nom sélectionné par le primaire).

    Label ``y = 1`` si le pari a **gagné** (rendement composé forward sur ``horizon``
    dans le sens du pari > 0). ``label_end`` = index de la barre de fin d'horizon,
    pour la purge/embargo à l'entraînement. Sans look-ahead : X à t, y sur t→t+h.
    """
    idx = scores.index
    fwd_simple = returns.shift(-1)  # rendement de t -> t+1 attribué à t
    rows: list[dict] = []
    for i, dt in enumerate(idx):
        if i + horizon >= len(idx):
            break  # horizon incomplet -> pas de label fiable
        row = scores.loc[dt].dropna()
        n = len(row)
        if n < 5:
            continue
        k = max(1, int(round(n * quantile)))
        ranked = row.sort_values()
        picks = {s: +1 for s in ranked.index[-k:]}  # longs
        picks.update({s: -1 for s in ranked.index[:k]})  # shorts
        # Rendement composé du pari sur l'horizon (t+1 .. t+h).
        window = fwd_simple.iloc[i : i + horizon]
        for sym, side in picks.items():
            if sym not in window.columns:
                continue
            compounded = float((1.0 + window[sym].fillna(0.0)).prod() - 1.0)
            feats = {}
            ok = True
            for fn in feature_names:
                fdf = features.get(fn)
                v = float(fdf.loc[dt, sym]) if (fdf is not None and sym in fdf.columns
                                                and dt in fdf.index) else np.nan
                if not np.isfinite(v):
                    ok = False
                    break
                feats[fn] = v
            if not ok:
                continue
            rows.append({
                "date": dt, "date_i": i, "label_end_i": i + horizon, "symbol": sym,
                "side": side, "y": 1 if side * compounded > 0 else 0, **feats,
            })
    return pd.DataFrame(rows)


def _simulate_book(weights_by_date: dict, daily_ret: pd.DataFrame, cost_rate: float):
    """Rejoue un book (poids par date de rééq., tenus entre deux) → (série nette, turnover, noms moyens)."""
    reb_dates = sorted(weights_by_date)
    if not reb_dates:
        return pd.Series(dtype=float), 0.0, 0.0
    days = daily_ret.index[(daily_ret.index >= reb_dates[0])]
    cur = pd.Series(dtype=float)
    prev_reb = pd.Series(dtype=float)
    net, tos, names = [], [], []
    reb_set = set(reb_dates)
    for dt in days:
        if dt in reb_set:
            new = weights_by_date[dt]
            idxu = new.index.union(prev_reb.index)
            to = float((new.reindex(idxu).fillna(0.0) - prev_reb.reindex(idxu).fillna(0.0)).abs().sum())
            cur = new
            prev_reb = new
            names.append(int((new.abs() > 1e-9).sum()))
        else:
            to = 0.0
        r = daily_ret.loc[dt]
        g = float((cur.reindex(r.index).fillna(0.0) * r.fillna(0.0)).sum())
        net.append(g - to * cost_rate)
        tos.append(to)
    return pd.Series(net, index=days), float(np.mean(tos)) if tos else 0.0, \
        float(np.mean(names)) if names else 0.0


def _norm_gross(w: pd.Series) -> pd.Series:
    g = w.abs().sum()
    return w / g if g > 0 else w


def walk_forward_meta(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    *,
    quantile: float = 0.2,
    horizon: int = 10,
    rebalance_every: int = 10,
    min_train: int = 400,
    embargo: int = 10,
    p_threshold: float = 0.5,
    cost_rate: float = 0.00025,
    feature_names: tuple[str, ...] = META_FEATURES,
) -> MetaResult:
    """Évalue raw vs méta (filtre/sizing) en walk-forward, purge+embargo, coûts inclus.

    À chaque date de rééquilibrage, entraîne la logistique sur les échantillons
    **passés à horizon clos** (``label_end_i + embargo ≤ date_i`` courant), prédit
    ``P(gain)`` pour les paris courants, et construit les books méta.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    samples = build_meta_samples(scores, returns, features, quantile=quantile,
                                 horizon=horizon, feature_names=feature_names)
    if samples.empty:
        return MetaResult(0, 0.0, 0.5, 0, 0, 0, 0, 0, 0, 0, 0)

    daily = returns
    reb_i = list(range(0, len(scores.index), rebalance_every))
    feats = list(feature_names)
    w_raw, w_filter, w_size = {}, {}, {}
    oos_correct: list[tuple[int, float]] = []  # (y, p) pour l'AUC OOS

    for i in reb_i:
        dt = scores.index[i]
        row = scores.loc[dt].dropna()
        if len(row) < 5:
            continue
        k = max(1, int(round(len(row) * quantile)))
        ranked = row.sort_values()
        sides = pd.Series(0.0, index=row.index)
        sides.loc[ranked.index[-k:]] = +1.0
        sides.loc[ranked.index[:k]] = -1.0
        picks = sides[sides != 0.0]
        w_raw[dt] = _norm_gross(picks.copy())

        # Entraînement : échantillons passés à horizon clos + embargo.
        train = samples[samples["label_end_i"] + embargo <= i]
        if len(train) < min_train or train["y"].nunique() < 2:
            # Pas encore de méta-modèle : méta = raw (mise en place).
            w_filter[dt] = _norm_gross(picks.copy())
            w_size[dt] = _norm_gross(picks.copy())
            continue

        Xtr = train[feats].to_numpy()
        ytr = train["y"].to_numpy()
        scaler = StandardScaler().fit(Xtr)
        clf = LogisticRegression(max_iter=1000, C=1.0).fit(scaler.transform(Xtr), ytr)

        # Features des paris courants (mêmes que build_meta_samples).
        cur_rows, cur_syms = [], []
        for sym in picks.index:
            vals = []
            ok = True
            for fn in feats:
                fdf = features.get(fn)
                v = float(fdf.loc[dt, sym]) if (fdf is not None and sym in fdf.columns
                                                and dt in fdf.index) else np.nan
                if not np.isfinite(v):
                    ok = False
                    break
                vals.append(v)
            if ok:
                cur_rows.append(vals)
                cur_syms.append(sym)
        if not cur_rows:
            w_filter[dt] = _norm_gross(picks.copy())
            w_size[dt] = _norm_gross(picks.copy())
            continue
        p = clf.predict_proba(scaler.transform(np.array(cur_rows)))[:, 1]
        p_ser = pd.Series(p, index=cur_syms)

        # Filtre : garder les paris p >= seuil ; sizing : pondérer par p.
        keep = picks[[s for s in cur_syms if p_ser[s] >= p_threshold]]
        w_filter[dt] = _norm_gross(keep.copy()) if len(keep) else pd.Series(dtype=float)
        sized = picks.reindex(cur_syms) * p_ser.reindex(cur_syms)
        w_size[dt] = _norm_gross(sized.dropna())

        # AUC OOS : évaluer le modèle sur les paris de CE rééq. (labels connus plus tard,
        # mais on ne les utilise QUE pour mesurer, jamais pour entraîner ce pas).
        cur_labels = samples[(samples["date_i"] == i) & (samples["symbol"].isin(cur_syms))]
        for _, rr in cur_labels.iterrows():
            oos_correct.append((int(rr["y"]), float(p_ser.get(rr["symbol"], 0.5))))

    raw_net, raw_to, raw_names = _simulate_book(w_raw, daily, cost_rate)
    filt_net, filt_to, filt_names = _simulate_book(w_filter, daily, cost_rate)
    size_net, size_to, _ = _simulate_book(w_size, daily, cost_rate)

    # AUC OOS (discrimination du méta-modèle) — best-effort.
    auc = 0.5
    try:
        from sklearn.metrics import roc_auc_score
        if oos_correct and len({y for y, _ in oos_correct}) == 2:
            auc = float(roc_auc_score([y for y, _ in oos_correct], [p for _, p in oos_correct]))
    except Exception:  # noqa: BLE001
        pass

    return MetaResult(
        n_samples=len(samples),
        base_win_rate=float(samples["y"].mean()),
        oos_auc=auc,
        raw_net_sharpe=_sharpe(raw_net),
        meta_filter_net_sharpe=_sharpe(filt_net),
        meta_size_net_sharpe=_sharpe(size_net),
        raw_turnover=raw_to, meta_filter_turnover=filt_to, meta_size_turnover=size_to,
        raw_avg_names=raw_names, meta_filter_avg_names=filt_names,
    )
