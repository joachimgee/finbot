"""Cadre d'exécution en couches enfichables (audit #5, inspiré de LEAN).

Sépare la décision de trading en **quatre étages remplaçables**, chacun avec un
contrat clair — au lieu d'un ``LiveTradingPipeline`` monolithique :

    Alpha  ─►  PortfolioConstruction  ─►  Risk  ─►  Execution
    data→signaux   signaux→poids cibles    veto/ajuste   poids→ordres soumis

Intérêt : tester/remplacer un étage sans toucher aux autres (p.ex. brancher un
autre modèle d'alpha, ou un exécuteur TWAP), et rendre le contrat de chaque couche
explicite. Les implémentations **par défaut** (``Pipeline*``) délèguent à la logique
déjà validée du pipeline : le comportement live est **inchangé**, seule la couture
devient explicite et injectable.

Les adaptateurs par défaut sont *duck-typed* sur un objet « pipeline » (ils
appellent ses méthodes) — ce module n'importe donc pas ``live_trading_pipeline``
(pas de cycle d'import).
"""
from __future__ import annotations

from typing import Dict, List, Protocol, Tuple, runtime_checkable


@runtime_checkable
class AlphaModel(Protocol):
    """Données de marché → signaux ``{symbole: score ∈ [-1,1]}``.

    Convention : un score ≤ 0 (ou l'absence de clé) = abstention / pas de conviction
    longue. Le modèle ne décide *pas* de la taille — c'est la construction.
    """

    def generate(self, data: Dict) -> Dict[str, float]:
        ...


@runtime_checkable
class PortfolioConstructionModel(Protocol):
    """Signaux → poids cibles ``{symbole: poids}`` (long-only, somme ≤ 1).

    C'est ici que vivent l'optimisation (Black-Litterman), le cap de concentration,
    l'overlay de volatilité et la bande de non-transaction (cost-aware).
    """

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        ...


@runtime_checkable
class RiskModel(Protocol):
    """Contrôle **pré-trade portefeuille** : valide (et peut ajuster) le book cible.

    Retourne ``(ok, weights)`` — ``ok=False`` => on s'abstient du rééquilibrage.
    Corrélation-aware (vol ex-ante / VaR / concentration).
    """

    def evaluate(
        self, weights: Dict[str, float], data: Dict
    ) -> Tuple[bool, Dict[str, float]]:
        ...


@runtime_checkable
class ExecutionModel(Protocol):
    """Poids cibles → ordres soumis (via l'unique gateway audité). Retourne les
    résultats d'exécution. ``dry_run`` applique tout sauf la soumission réelle."""

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        ...


# --- Implémentations par défaut : délèguent au pipeline (comportement inchangé) ---


class PipelineAlpha:
    """Alpha par défaut : signaux validés + abstention (``_generate_signals``)."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def generate(self, data: Dict) -> Dict[str, float]:
        return self._p._generate_signals(data)


class PipelineConstruction:
    """Construction par défaut : BL + cap + overlay vol + bande cost-aware."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        return self._p._construct_weights(signals, data)


class HRPConstruction:
    """Construction **HRP** : le signal *sélectionne* les noms, HRP les *dimensionne*.

    Alternative enfichable à la construction BL. Le momentum choisit les titres à
    conviction longue (signal > 0) ; Hierarchical Risk Parity (López de Prado) les
    pondère de façon **robuste au bruit de covariance** (pas d'inversion de matrice),
    puis on applique la même finalisation (cap → vol → bande) que la construction par
    défaut. Données insuffisantes / trop peu de noms → repli sur la construction BL
    (fail-safe, jamais de crash).
    """

    def __init__(self, pipeline: object, lookback: int = 252, min_names: int = 3) -> None:
        self._p = pipeline
        self.lookback = lookback
        self.min_names = min_names

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        import pandas as pd

        from financial_analyzer.portfolio.hrp import hrp_weights

        longs = [s for s, v in (signals or {}).items() if v and v > 0]
        prices = (data or {}).get("prices", {}) or {}
        frames = {s: prices[s]["close"] for s in longs
                  if s in prices and prices[s] is not None
                  and not prices[s].empty and "close" in prices[s]}
        if len(frames) < self.min_names:
            return self._p._construct_weights(signals, data)  # repli BL
        try:
            close = pd.DataFrame(frames).dropna(how="all").tail(self.lookback + 1)
            rets = close.pct_change().dropna()
            w = hrp_weights(rets)
            weights = {s: float(x) for s, x in w.items() if x > 1e-9}
            if not weights:
                return self._p._construct_weights(signals, data)
            return self._p._finalize_weights(weights, data)
        except Exception:  # noqa: BLE001 - une construction ne doit jamais crasher le run
            return self._p._construct_weights(signals, data)


class MultiStrategyConstruction:
    """Construction **multi-stratégie** (momentum + PCA-résiduel + paires).

    Ignore le signal du pipeline et calcule le **book combiné long/short** depuis
    ``data['prices']`` (familles décorrélées, mélangées par risk-weighting). Repli
    sur la construction BL si données insuffisantes.

    ⚠️ Long/short + familles **non validées** (seul momentum l'est) → **paper
    uniquement** (forward-test). On ne passe **pas** par la finalisation long-only
    (cap/vol) : les poids sont déjà normalisés (brut = 1) par le book. En revanche,
    la **bande de non-transaction** (``pipeline.no_trade_band``, opt-in) est
    appliquée si activée : elle est sign-agnostique (``|cible − détenu|`` par actif),
    donc valable en long/short — elle ne bouge une ligne que si son poids change de
    plus que la bande, réduisant le churn du rééquilibrage quotidien (coûts).
    """

    def __init__(self, pipeline: object, family_weights: Dict[str, float] | None = None,
                 min_names: int = 10) -> None:
        self._p = pipeline
        self.family_weights = family_weights
        self.min_names = min_names

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        import pandas as pd

        from financial_analyzer.trading.multi_strategy_book import combined_book

        prices = (data or {}).get("prices", {}) or {}
        frames = {s: df["close"] for s, df in prices.items()
                  if df is not None and not df.empty and "close" in df}
        if len(frames) < self.min_names:
            return self._p._construct_weights(signals, data)
        close = pd.DataFrame(frames).dropna(how="all")
        book = combined_book(close, self.family_weights)
        if not book:
            return self._p._construct_weights(signals, data)
        # Bande de non-transaction (opt-in) : tenir les lignes dont le poids bouge
        # de moins que la bande vs le book détenu — évite de churner le book pour
        # des micro-variations de signal (coûts). Sign-agnostique -> OK en long/short.
        if getattr(self._p, "no_trade_band", 0.0) > 0:
            book = self._p._apply_no_trade_band(book)
        return book


class MetaLabelConstruction:
    """Construction **méta-labeling** : momentum 12-1 filtré par un modèle secondaire.

    Le primaire (momentum 12-1 cross-section, long/short) décide la **direction** ;
    un modèle secondaire (logistique) prédit ``P(gain)`` d'un pari et **ne garde que
    P ≥ seuil** (cf. ``backtest/meta_labeling``). Entraîné *à chaud* sur tout
    l'historique à label clos (purge+embargo). Repli sur la construction BL si données
    insuffisantes.

    ⚠️ **Discipline** : le méta-labeling a passé les contrôles d'artefact sur 18 ans
    (bat 100 % de l'aléatoire, AUC p=0.002) **mais** reste sous **biais de survie**
    (survivants) et sans DSR campagne → **paper uniquement** (forward-test). Long/short.
    On applique la bande de non-transaction (opt-in) comme le multi-stratégie.
    """

    def __init__(self, pipeline: object, quantile: float = 0.2, rebalance_every: int = 10,
                 p_threshold: float = 0.5, min_train: int = 400, min_names: int = 10,
                 lookback_days: int = 1100) -> None:
        self._p = pipeline
        self.quantile = quantile
        self.rebalance_every = rebalance_every
        self.p_threshold = p_threshold
        self.min_train = min_train
        self.min_names = min_names
        # Le méta a besoin de ~3 ans (momentum 12-1 = 252 j + assez de dates pour
        # accumuler min_train échantillons à label clos). Le fetch par défaut du
        # pipeline (~420 j) ne suffit pas → on récupère notre propre panel long.
        self.lookback_days = lookback_days

    def _long_panel(self, data: Dict):
        """Panel de clôtures ~3 ans : fetch broker si possible, sinon données pipeline."""
        import pandas as pd

        broker = getattr(self._p, "broker", None)
        tickers = list(getattr(self._p, "tickers", []) or [])
        if broker is not None and tickers and hasattr(broker, "get_bars_multi"):
            try:
                from datetime import datetime, timedelta

                end = datetime.now()  # noqa: DTZ005
                multi = broker.get_bars_multi(tickers, end - timedelta(days=self.lookback_days), end)
                frames = {s: df["close"] for s, df in (multi or {}).items()
                          if df is not None and not df.empty and "close" in df}
                if len(frames) >= self.min_names:
                    return pd.DataFrame(frames).dropna(how="all")
            except Exception:  # noqa: BLE001 - repli sur les données du pipeline
                pass
        prices = (data or {}).get("prices", {}) or {}
        frames = {s: df["close"] for s, df in prices.items()
                  if df is not None and not df.empty and "close" in df}
        return pd.DataFrame(frames).dropna(how="all") if frames else pd.DataFrame()

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        from financial_analyzer.backtest.classic_factors import (
            compute_classic_factors,
            daily_returns,
        )
        from financial_analyzer.backtest.meta_labeling import (
            META_FEATURES_RICH,
            meta_filter_today,
            regime_features,
        )

        close = self._long_panel(data)
        if close.shape[1] < self.min_names:
            return self._p._construct_weights(signals, data)  # repli BL
        try:
            factors = compute_classic_factors(close)
            scores = factors.get("momentum_12_1")
            if scores is None or scores.dropna(how="all").empty:
                return self._p._construct_weights(signals, data)
            # Jeu enrichi (features titre + régime marché) — le modèle pré-enregistré.
            factors.update(regime_features(close, scores))
            book = meta_filter_today(
                scores, daily_returns(close), factors,
                quantile=self.quantile, horizon=self.rebalance_every,
                min_train=self.min_train, p_threshold=self.p_threshold,
                feature_names=META_FEATURES_RICH)
        except Exception:  # noqa: BLE001 - une construction ne doit jamais crasher le run
            return self._p._construct_weights(signals, data)
        if not book:
            return self._p._construct_weights(signals, data)
        # Contrôle de drawdown (opt-in) : overlay de vol-targeting (Barroso). Le
        # Monte-Carlo a montré un drawdown sévère du L/S momentum ; scaler l'exposition
        # vers target_vol (dé-risque en régime turbulent, max_exposure=1 → jamais de
        # levier) divise ~par 2 le drawdown en préservant le Sharpe. Ordre = vol → bande
        # (comme _finalize_weights).
        if getattr(self._p, "target_vol", None):
            book = self._p._apply_vol_overlay(book, data)
        # Bande de non-transaction (opt-in), sign-agnostique → OK long/short.
        if getattr(self._p, "no_trade_band", 0.0) > 0:
            book = self._p._apply_no_trade_band(book)
        return book


class AmihudConstruction:
    """Construction **illiquidité d'Amihud** (2002) sur small-caps — long/short.

    Score = ``moyenne(|rendement| / $volume)`` sur ``window`` jours : élevé = illiquide.
    Book long/short cross-section : **long les plus illiquides**, **short les plus
    liquides** (prime d'illiquidité). Utilise les volumes du panel fourni par le
    pipeline (``data['prices'][sym]['volume']``).

    ⚠️ **Discipline** : ce facteur a montré le meilleur profil de la campagne (Sharpe L/S
    net +1.55, t=3.72, stable sur 3 régimes, robuste jusqu'à 300 bps) **mais** il est
    celui où le **biais de survie** frappe le plus fort (acheter les plus illiquides =
    acheter les futurs radiés, absents des panels historiques). → **paper uniquement**,
    le forward-test étant justement exempt de ce biais.
    """

    def __init__(self, pipeline: object, window: int | None = None,
                 quantile: float | None = None, min_names: int | None = None,
                 lookback_days: int = 400, consolidated_volume: bool = True,
                 spec: object | None = None) -> None:
        # Paramètres par défaut : ceux de la spécification VALIDÉE, pas des valeurs de
        # confort réécrites ici. Un appelant peut toujours surcharger explicitement.
        from financial_analyzer.backtest.illiquidity import DEFAULT_SPEC

        sp = spec or DEFAULT_SPEC
        self._p = pipeline
        self.spec = sp
        self.window = sp.window if window is None else window
        self.quantile = sp.quantile if quantile is None else quantile
        self.min_names = sp.min_names if min_names is None else min_names
        self.min_history_frac = sp.min_history_frac
        self.lookback_days = lookback_days
        # ⚠️ CRITIQUE : le feed Alpaca IEX ne rapporte que le volume de la bourse IEX
        # (~4 % du consolidé, ratio mesuré 20-73×). Amihud calculé dessus est un proxy
        # dégradé (Sharpe +1.55 vs +3.48 sur la même période avec le volume consolidé).
        # On récupère donc les volumes CONSOLIDÉS (Yahoo) pour la décision.
        self.consolidated_volume = consolidated_volume

    def _panels(self, data: Dict):
        """(close, volume) — volumes **consolidés** (Yahoo) si disponibles."""
        import pandas as pd

        if self.consolidated_volume:
            try:
                from datetime import datetime, timedelta

                from financial_analyzer.data.yahoo_history import fetch_daily_ohlcv_yahoo

                tickers = list(getattr(self._p, "tickers", []) or [])
                end = datetime.now()  # noqa: DTZ005
                start = end - timedelta(days=self.lookback_days)
                o = fetch_daily_ohlcv_yahoo(tickers, start.strftime("%Y-%m-%d"),
                                            end.strftime("%Y-%m-%d"))
                if len(o) >= self.min_names:
                    c = pd.DataFrame({s: d["close"] for s, d in o.items()}).sort_index()
                    v = pd.DataFrame({s: d["volume"] for s, d in o.items()}).sort_index()
                    return c.ffill().dropna(how="all"), v
            except Exception:  # noqa: BLE001 - repli sur les données du pipeline
                pass
        prices = (data or {}).get("prices", {}) or {}
        closes, vols = {}, {}
        for s, df in prices.items():
            if df is None or df.empty or "close" not in df or "volume" not in df:
                continue
            closes[s] = df["close"]
            vols[s] = df["volume"]
        if not closes:
            return pd.DataFrame(), pd.DataFrame()
        return pd.DataFrame(closes).dropna(how="all"), pd.DataFrame(vols)

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        # Définition du signal : **importée**, jamais recalculée ici. Le backtest, le
        # moniteur et ce book live appellent les mêmes fonctions — c'est ce qui rend
        # une divergence de définition impossible plutôt qu'improbable
        # (cf. backtest/illiquidity.py, et tests/test_backtest/test_amihud_parity.py
        # qui vérifie que les deux chemins produisent le même book).
        from financial_analyzer.backtest.illiquidity import (
            amihud_illiquidity,
            amihud_weights,
            prepare_panels,
        )

        close_df, vol_df = self._panels(data)
        if close_df.shape[1] < self.min_names:
            return self._p._construct_weights(signals, data)  # repli BL
        try:
            close, vol = prepare_panels(close_df, vol_df,
                                        min_history_frac=self.min_history_frac)
            amihud = amihud_illiquidity(close, vol, window=self.window)
            if amihud.empty:
                return self._p._construct_weights(signals, data)
            w = amihud_weights(amihud.iloc[-1], quantile=self.quantile,
                               min_names=self.min_names)
            book = {s: float(x) for s, x in w.items() if abs(x) > 1e-9}
        except Exception:  # noqa: BLE001 - une construction ne doit jamais crasher le run
            return self._p._construct_weights(signals, data)
        if not book:
            return self._p._construct_weights(signals, data)
        if getattr(self._p, "target_vol", None):
            book = self._p._apply_vol_overlay(book, data)
        if getattr(self._p, "no_trade_band", 0.0) > 0:
            book = self._p._apply_no_trade_band(book)
        return book


class PipelineRisk:
    """Risque par défaut : contrôle pré-trade portefeuille (``_portfolio_risk_ok``)."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def evaluate(
        self, weights: Dict[str, float], data: Dict
    ) -> Tuple[bool, Dict[str, float]]:
        ok = True if not weights else self._p._portfolio_risk_ok(weights, data)
        return ok, weights


class PipelineExecution:
    """Exécution par défaut : génération d'ordres + chokepoint audité."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        orders = self._p._generate_orders(target_weights, data)
        return self._p._execute_orders_with_risk_checks(orders, dry_run=dry_run)


class ScheduledExecution:
    """ExecutionModel qui **découpe** chaque ordre en tranches enfants (algo TWAP /
    Almgren-Chriss), soumises via le **même gateway audité**.

    Chaque tranche porte une ``idempotency_key`` unique (indice de tranche) pour ne
    pas être dédupliquée par la clé dérivée. ``kappa=0`` ⇒ TWAP (tranches égales) ;
    ``kappa>0`` ⇒ front-loaded (Almgren-Chriss, urgence).

    ⚠️ **Étalement dans le temps** : ce modèle produit et soumet le *planning* ; le
    véritable espacement intraday exige un driver d'exécution temps-réel (hors
    périmètre). En synchrone, les tranches partent en séquence — l'intérêt est le
    *plumbing* (découpe + clés idempotentes + passage par le chokepoint), prêt à
    recevoir un driver. Le bénéfice d'impact ne se matérialise qu'avec l'espacement.
    """

    def __init__(self, pipeline: object, n_slices: int = 5, kappa: float = 0.0,
                 min_slice_qty: int = 1) -> None:
        self._p = pipeline
        self.n_slices = max(1, int(n_slices))
        self.kappa = float(kappa)
        self.min_slice_qty = max(1, int(min_slice_qty))

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        from financial_analyzer.trading.execution_algos import almgren_chriss_schedule

        parents = self._p._generate_orders(target_weights, data)
        children: List[Dict] = []
        for o in parents:
            qty = int(o.get("qty", 0))
            if qty <= 0 or qty < self.min_slice_qty:
                children.append(o)
                continue
            schedule = almgren_chriss_schedule(qty, self.n_slices, self.kappa)
            for i, child_qty in enumerate(schedule):
                if child_qty < self.min_slice_qty:
                    continue
                children.append({
                    **o, "qty": child_qty,
                    "idempotency_key": f"{o['symbol']}:{o['side']}:s{i}:{child_qty}",
                })
        return self._p._execute_orders_with_risk_checks(children, dry_run=dry_run)


__all__ = [
    "AlphaModel",
    "ExecutionModel",
    "HRPConstruction",
    "MultiStrategyConstruction",
    "PipelineAlpha",
    "PipelineConstruction",
    "PipelineExecution",
    "PipelineRisk",
    "PortfolioConstructionModel",
    "ScheduledExecution",
    "RiskModel",
]
