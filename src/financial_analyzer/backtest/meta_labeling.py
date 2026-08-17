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

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = ["MetaResult", "MetaConfirm", "META_FEATURES", "META_FEATURES_RICH",
           "REGIME_FEATURES", "regime_features", "build_meta_samples",
           "walk_forward_meta", "confirm_meta_labeling", "meta_filter_today"]

#: Features méta par défaut (clés de ``compute_classic_factors``), motivées ex-ante.
META_FEATURES = ("momentum_12_1", "momentum_6_1", "low_vol", "reversal_5", "max_lottery")

#: Features de **régime** (Daniel-Moskowitz 2016, Barroso-Santa-Clara 2015) : ce qui
#: prédit les *krachs de momentum* n'est pas une caractéristique cross-section du titre
#: mais l'état du marché. Diffusées (mêmes valeurs pour tous les titres un jour donné).
REGIME_FEATURES = ("mkt_ret_126", "mkt_vol_21", "xs_disp")

#: Jeu enrichi = caractéristiques titre + régime marché. Pré-enregistré (pas un sweep).
META_FEATURES_RICH = META_FEATURES + REGIME_FEATURES


def regime_features(close: pd.DataFrame, scores: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Features de régime diffusées (dates × titres, mêmes valeurs par ligne).

    * ``mkt_ret_126`` — rendement cumulé du marché équipondéré sur 126 j (état
      haussier/baissier ; le momentum krache après un bear market qui rebondit) ;
    * ``mkt_vol_21`` — vol réalisée du marché sur 21 j (turbulence — Barroso) ;
    * ``xs_disp`` — dispersion cross-section du score momentum du jour (régimes de
      forte/faible dispersion).
    """
    mkt_ret = close.pct_change().mean(axis=1)
    mkt_ret_126 = (1.0 + mkt_ret).rolling(126).apply(lambda x: x.prod(), raw=True) - 1.0
    mkt_vol_21 = mkt_ret.rolling(21).std()
    xs_disp = scores.std(axis=1)  # std cross-section par date

    def _broadcast(s: pd.Series) -> pd.DataFrame:
        return pd.DataFrame({c: s for c in close.columns}, index=close.index)

    return {"mkt_ret_126": _broadcast(mkt_ret_126), "mkt_vol_21": _broadcast(mkt_vol_21),
            "xs_disp": _broadcast(xs_disp)}


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
                "side": side, "y": 1 if side * compounded > 0 else 0,
                "bet_ret": float(side * compounded), **feats,
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
    max_train: int | None = None,
) -> MetaResult:
    """Évalue raw vs méta (filtre/sizing) en walk-forward, purge+embargo, coûts inclus.

    À chaque date de rééquilibrage, entraîne la logistique sur les échantillons
    **passés à horizon clos** (``label_end_i + embargo ≤ date_i`` courant), prédit
    ``P(gain)`` pour les paris courants, et construit les books méta.

    ``max_train`` (optionnel) plafonne la fenêtre d'entraînement aux N échantillons
    les plus récents — borne le coût du cas quotidien et compare les cadences à
    fenêtre égale.
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
        if max_train is not None and len(train) > max_train:
            train = train.tail(max_train)
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


def _maxdd(net: pd.Series) -> float:
    """Max drawdown (%) d'une série de rendements nets."""
    eq = (1.0 + pd.Series(net).dropna()).cumprod()
    return float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) else 0.0


def compare_meta_sizing(
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
    kelly_fraction: float = 0.25,
    max_train: int | None = None,
) -> dict[str, dict[str, float]]:
    """Compare le **sizing** des paris retenus par le méta (López de Prado ch.10).

    Trois schémas sur les *mêmes* paris retenus (P ≥ seuil), la logistique n'étant
    entraînée qu'une fois par rééq. :

    * ``equal`` — équipondéré (le book méta actuel), brut = 1 ;
    * ``confidence`` — taille ∝ ``bet_size_from_probability(P)`` (AFML 10.1), brut = 1
      (réalloue par conviction, exposition totale identique) ;
    * ``kelly`` — Kelly fractionnaire ``f=0.25`` par pari (ratio gain/perte estimé sur
      l'historique), **brut variable capé à 1** (parie plus quand la conviction moyenne
      est haute, dé-lève quand elle est basse — jamais de levier).

    Renvoie ``{schéma: {net_sharpe, turnover, maxdd, avg_gross}}``.
    """
    from financial_analyzer.trading.bet_sizing import bet_size_from_probability, kelly_criterion

    samples = build_meta_samples(scores, returns, features, quantile=quantile,
                                 horizon=horizon, feature_names=feature_names)
    if samples.empty:
        return {}
    # Ratio gain/perte global (Kelly b) estimé sur les paris à label clos.
    br = samples["bet_ret"].to_numpy()
    win, loss = br[br > 0], -br[br < 0]
    b = float(win.mean() / loss.mean()) if len(win) and len(loss) and loss.mean() > 0 else 1.0

    feats = list(feature_names)
    reb_i = list(range(0, len(scores.index), rebalance_every))
    w_eq: dict = {}
    w_conf: dict = {}
    w_kelly: dict = {}
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

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

        train = samples[samples["label_end_i"] + embargo <= i]
        if max_train is not None and len(train) > max_train:
            train = train.tail(max_train)
        if len(train) < min_train or train["y"].nunique() < 2:
            for wd in (w_eq, w_conf, w_kelly):
                wd[dt] = _norm_gross(picks.copy())
            continue
        scaler = StandardScaler().fit(train[feats].to_numpy())
        clf = LogisticRegression(max_iter=1000, C=1.0).fit(
            scaler.transform(train[feats].to_numpy()), train["y"].to_numpy())
        rows, syms = [], []
        for sym in picks.index:
            vals, ok = [], True
            for fn in feats:
                fdf = features.get(fn)
                v = float(fdf.loc[dt, sym]) if (fdf is not None and sym in fdf.columns
                                                and dt in fdf.index) else np.nan
                if not np.isfinite(v):
                    ok = False
                    break
                vals.append(v)
            if ok:
                rows.append(vals)
                syms.append(sym)
        if not rows:
            for wd in (w_eq, w_conf, w_kelly):
                wd[dt] = _norm_gross(picks.copy())
            continue
        p = pd.Series(clf.predict_proba(scaler.transform(np.array(rows)))[:, 1], index=syms)
        keep = [s for s in syms if p[s] >= p_threshold]
        if not keep:
            for wd in (w_eq, w_conf, w_kelly):
                wd[dt] = pd.Series(dtype=float)
            continue
        kp = picks[keep]
        # equal
        w_eq[dt] = _norm_gross(kp.copy())
        # confidence (AFML 10.1), brut=1
        conf = pd.Series({s: bet_size_from_probability(float(p[s]), 2, side=int(kp[s]),
                                                       kelly_fraction=1.0) for s in keep})
        w_conf[dt] = _norm_gross(conf) if conf.abs().sum() > 0 else _norm_gross(kp.copy())
        # kelly fractionnaire, brut variable capé à 1
        kel = pd.Series({s: kelly_criterion(float(p[s]), b, kelly_fraction=kelly_fraction) * int(kp[s])
                         for s in keep})
        g = kel.abs().sum()
        w_kelly[dt] = (kel / g if g > 1.0 else kel) if g > 0 else _norm_gross(kp.copy())

    out = {}
    for name, wd in (("equal", w_eq), ("confidence", w_conf), ("kelly", w_kelly)):
        net, to, _ = _simulate_book(wd, returns, cost_rate)
        gross = float(np.mean([w.abs().sum() for w in wd.values() if len(w)])) if wd else 0.0
        out[name] = {"net_sharpe": _sharpe(net), "turnover": to,
                     "maxdd": _maxdd(net), "avg_gross": gross}
    out["_kelly_b"] = {"win_loss_ratio": b}
    return out


def meta_filter_today(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    *,
    quantile: float = 0.2,
    horizon: int = 10,
    min_train: int = 400,
    embargo: int = 10,
    p_threshold: float = 0.5,
    feature_names: tuple[str, ...] = META_FEATURES,
) -> dict[str, float]:
    """Poids **du jour** (dernière date) du book momentum FILTRÉ par le méta-modèle.

    Version « live » de :func:`walk_forward_meta` : entraîne la logistique sur **tout
    l'historique à label clos** (purge + embargo), prédit ``P(gain)`` pour les paris
    du primaire *aujourd'hui*, et ne garde que ``P ≥ seuil`` (long/short, brut≈1).

    Fail-safe : données insuffisantes / erreur → renvoie les poids du primaire **non
    filtrés** (jamais d'exception ; on ne casse pas la décision). Renvoie ``{}`` si
    aucun pari aujourd'hui.
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except Exception:  # noqa: BLE001 - sans sklearn, pas de méta : on rend le primaire
        return _raw_picks_today(scores, quantile)

    if scores.empty or len(scores.index) < horizon + 2:
        return _raw_picks_today(scores, quantile)
    last_i = len(scores.index) - 1
    dt = scores.index[last_i]

    picks = _raw_picks_series_today(scores, quantile)
    if picks.empty:
        return {}
    feats = list(feature_names)

    try:
        samples = build_meta_samples(scores, returns, features, quantile=quantile,
                                     horizon=horizon, feature_names=feats)
        train = samples[samples["label_end_i"] + embargo <= last_i]
        if len(train) < min_train or train["y"].nunique() < 2:
            return {s: float(w) for s, w in picks.items()}  # pas encore de méta

        scaler = StandardScaler().fit(train[feats].to_numpy())
        clf = LogisticRegression(max_iter=1000, C=1.0).fit(
            scaler.transform(train[feats].to_numpy()), train["y"].to_numpy())

        rows, syms = [], []
        for sym in picks.index:
            vals, ok = [], True
            for fn in feats:
                fdf = features.get(fn)
                v = float(fdf.loc[dt, sym]) if (fdf is not None and sym in fdf.columns
                                                and dt in fdf.index) else np.nan
                if not np.isfinite(v):
                    ok = False
                    break
                vals.append(v)
            if ok:
                rows.append(vals)
                syms.append(sym)
        if not rows:
            return {s: float(w) for s, w in picks.items()}
        p = clf.predict_proba(scaler.transform(np.array(rows)))[:, 1]
        keep = [syms[j] for j in range(len(syms)) if p[j] >= p_threshold]
        kept = picks[keep] if keep else pd.Series(dtype=float)
        kept = _norm_gross(kept)
        return {s: float(w) for s, w in kept.items() if abs(w) > 1e-9}
    except Exception:  # noqa: BLE001 - le méta ne doit jamais casser la décision
        return {s: float(w) for s, w in picks.items()}


def _raw_picks_series_today(scores: pd.DataFrame, quantile: float) -> pd.Series:
    """Paris long/short (±1, brut normalisé) du primaire à la dernière date."""
    if scores.empty:
        return pd.Series(dtype=float)
    row = scores.iloc[-1].dropna()
    if len(row) < 5:
        return pd.Series(dtype=float)
    k = max(1, int(round(len(row) * quantile)))
    ranked = row.sort_values()
    sides = pd.Series(0.0, index=row.index)
    sides.loc[ranked.index[-k:]] = +1.0
    sides.loc[ranked.index[:k]] = -1.0
    return _norm_gross(sides[sides != 0.0])


def _raw_picks_today(scores: pd.DataFrame, quantile: float) -> dict[str, float]:
    return {s: float(w) for s, w in _raw_picks_series_today(scores, quantile).items()}


@dataclass
class MetaConfirm:
    """Résultat de la passe de confirmation rigoureuse du méta-filtre."""

    raw_sharpe: float
    meta_sharpe: float
    rand_sharpe_mean: float
    rand_sharpe_p95: float
    meta_percentile_vs_random: float  # % de filtres aléatoires battus par le méta
    n_random: int
    auc: float
    auc_perm_pvalue: float            # P(AUC_aléatoire ≥ AUC_méta) sous labels mélangés
    n_oos_preds: int
    subperiod_meta_sharpes: list[float]
    subperiod_raw_sharpes: list[float]
    avg_kept: float
    meta_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    def summary(self) -> str:
        return (
            f"raw {self.raw_sharpe:+.2f} | méta {self.meta_sharpe:+.2f} | "
            f"filtres ALÉATOIRES (même #noms) {self.rand_sharpe_mean:+.2f} (p95 {self.rand_sharpe_p95:+.2f}) "
            f"→ méta bat {self.meta_percentile_vs_random:.0f}% des aléatoires | "
            f"AUC {self.auc:.3f} (p-perm {self.auc_perm_pvalue:.3f})"
        )


def confirm_meta_labeling(
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
    n_random: int = 100,
    n_perm: int = 1000,
    seed: int = 0,
) -> MetaConfirm:
    """Confirme (ou infirme) l'edge du méta-filtre par CONTRÔLES d'artefact.

    Trois contrôles, la logistique n'est entraînée qu'une fois par rééq. :

    1. **Filtre aléatoire** : à chaque date, on filtre les paris du primaire vers le
       *même nombre de noms* que le méta, mais **au hasard** (``n_random`` tirages).
       Si le méta ne bat pas nettement cette distribution nulle, son Sharpe vient de
       la **concentration/turnover**, pas d'une compétence du modèle.
    2. **Permutation de l'AUC** : labels OOS mélangés ``n_perm`` fois → p-value du
       pouvoir discriminant réel.
    3. **Stabilité par sous-période** (tiers) : l'edge est-il partout ou dans une
       seule fenêtre chanceuse ?
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    samples = build_meta_samples(scores, returns, features, quantile=quantile,
                                 horizon=horizon, feature_names=feature_names)
    rng = np.random.default_rng(seed)
    feats = list(feature_names)
    reb_i = list(range(0, len(scores.index), rebalance_every))
    w_raw: dict = {}
    w_meta: dict = {}
    w_rand: list[dict] = [dict() for _ in range(n_random)]
    oos_y: list[int] = []
    oos_p: list[float] = []
    kept_counts: list[int] = []

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

        train = samples[samples["label_end_i"] + embargo <= i]
        if len(train) < min_train or train["y"].nunique() < 2:
            w_meta[dt] = _norm_gross(picks.copy())
            for r in range(n_random):
                w_rand[r][dt] = _norm_gross(picks.copy())
            continue

        scaler = StandardScaler().fit(train[feats].to_numpy())
        clf = LogisticRegression(max_iter=1000, C=1.0).fit(
            scaler.transform(train[feats].to_numpy()), train["y"].to_numpy())

        cur_rows, cur_syms = [], []
        for sym in picks.index:
            vals, ok = [], True
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
            w_meta[dt] = _norm_gross(picks.copy())
            for r in range(n_random):
                w_rand[r][dt] = _norm_gross(picks.copy())
            continue
        p = clf.predict_proba(scaler.transform(np.array(cur_rows)))[:, 1]
        p_ser = pd.Series(p, index=cur_syms)
        keep = [s for s in cur_syms if p_ser[s] >= p_threshold]
        kk = len(keep)
        kept_counts.append(kk)
        w_meta[dt] = _norm_gross(picks[keep].copy()) if kk else pd.Series(dtype=float)
        # Filtres aléatoires : kk noms tirés au hasard parmi les mêmes paris.
        for r in range(n_random):
            if kk == 0:
                w_rand[r][dt] = pd.Series(dtype=float)
            else:
                sel = rng.choice(cur_syms, size=min(kk, len(cur_syms)), replace=False)
                w_rand[r][dt] = _norm_gross(picks[list(sel)].copy())
        # AUC OOS : labels connus de ce rééq.
        cur = samples[(samples["date_i"] == i) & (samples["symbol"].isin(cur_syms))]
        for _, rr in cur.iterrows():
            oos_y.append(int(rr["y"]))
            oos_p.append(float(p_ser.get(rr["symbol"], 0.5)))

    raw_ser = _simulate_book(w_raw, returns, cost_rate)[0]
    meta_ser = _simulate_book(w_meta, returns, cost_rate)[0]
    rand_sharpes = np.array([_sharpe(_simulate_book(w_rand[r], returns, cost_rate)[0])
                             for r in range(n_random)])
    meta_sh = _sharpe(meta_ser)

    # AUC + permutation.
    auc, auc_p = 0.5, 1.0
    try:
        from sklearn.metrics import roc_auc_score
        y = np.array(oos_y)
        pp = np.array(oos_p)
        if len(y) and len(set(y)) == 2:
            auc = float(roc_auc_score(y, pp))
            ge = 0
            for _ in range(n_perm):
                ge += roc_auc_score(rng.permutation(y), pp) >= auc
            auc_p = float((ge + 1) / (n_perm + 1))
    except Exception:  # noqa: BLE001
        pass

    # Sous-périodes (tiers) sur la série méta et raw.
    def _thirds(s: pd.Series) -> list[float]:
        s = s.dropna()
        n = len(s) // 3
        return [_sharpe(s.iloc[a:b]) for a, b in [(0, n), (n, 2 * n), (2 * n, len(s))]] if n else [0, 0, 0]

    pct = float((meta_sh > rand_sharpes).mean() * 100.0) if n_random else float("nan")
    return MetaConfirm(
        raw_sharpe=_sharpe(raw_ser), meta_sharpe=meta_sh,
        rand_sharpe_mean=float(rand_sharpes.mean()) if n_random else float("nan"),
        rand_sharpe_p95=float(np.percentile(rand_sharpes, 95)) if n_random else float("nan"),
        meta_percentile_vs_random=pct, n_random=n_random,
        auc=auc, auc_perm_pvalue=auc_p, n_oos_preds=len(oos_y),
        subperiod_meta_sharpes=_thirds(meta_ser), subperiod_raw_sharpes=_thirds(raw_ser),
        avg_kept=float(np.mean(kept_counts)) if kept_counts else 0.0,
        meta_returns=meta_ser.dropna(),
    )
