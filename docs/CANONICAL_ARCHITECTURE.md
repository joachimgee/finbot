# FinBot — Architecture réelle (chemin canonique)

> Décrit le système **tel qu'il est**, pas tel qu'il fut planifié. Les anciens
> « plans d'intégration » et « rapports de livraison » aspirationnels sont
> déplacés dans [`docs/archive/`](archive/). La source de vérité de l'état et du
> plan est [`SYSTEM_ASSESSMENT_AND_ROADMAP.md`](SYSTEM_ASSESSMENT_AND_ROADMAP.md) ;
> la mise en production est décrite par [`RUNBOOK_PAPER_TO_LIVE.md`](RUNBOOK_PAPER_TO_LIVE.md).

## But

Trading actions US **automatisé, sûreté d'abord**, paper → live via Alpaca. Un
seul chemin place des ordres ; rien ne trade sur un signal non validé ; rien ne
touche au live sans double verrou explicite.

## Le chemin argent canonique (un seul)

```
scripts/professional_analysis_daemon.py   ← l'unique entrée qui place des ordres
   │
   ├─ universe/…                     sélection d'univers + filtre de tradabilité
   ├─ intégration/signal_fusion + compute_professional_score
   │      signaux : technical + sentiment RÉELS ; sources sans modèle → ABSTENTION
   ├─ trading/live_trading_pipeline.compute_target_weights
   │      allocation Black-Litterman inclinée par le signal 12-1 validé,
   │      plafonnée au cap de concentration du RiskGuard
   ├─ trading/rebalance_gate         ne rééquilibre que tous les 10 jours ouvrés
   │                                 (cadence validée OOS, persistée)
   └─ trading/order_gateway.submit   ← CHOKEPOINT UNIQUE audité
          1. garde de mode (paper/live)   2. idempotence
          3. RiskGuard (limites + circuit breaker)   4. audit + journal
          5. soumission broker (BrokerAdapter Alpaca)
   puis : réconciliation journal↔broker, snapshots P&L, alertes
```

**Invariants vérifiés en CI** (`tests/test_scripts/test_daemon_safety_invariants.py`) :
aucun appel `submit_order` hors du gateway ; le score de décision n'est jamais une
constante.

## Signaux : ce qui décide réellement

- **Portail de validation** (`backtest/validation_gate.py`) : un signal n'entre
  dans la décision que s'il passe **IC t > 2 ET Sharpe net > 0** OOS (directionnel).
  Le registre `VALIDATED_SIGNALS` est la source unique de vérité.
- **Validé à ce jour : `momentum_12_1` seul** (12-1 momentum, reb=10, IC t 2.56,
  Sharpe net +0.76). Les facteurs value/quality n'ont **pas** d'edge validé sur
  l'univers testé ; le combinateur ridge est écarté (Sharpe positif = artefact de
  queue, IC négatif).
- **Abstention** : toute source sans modèle validé/entraîné (fundamental, ml_lstm,
  ml_factor, rl) retourne `None` au lieu d'injecter une constante — elle ne dilue
  pas la décision.

## Sûreté

- **Double verrou paper/live** (`trading/safety.py`) : le daemon est câblé
  `mode='paper'` ; le live exige *en plus* `FINBOT_ENABLE_LIVE_TRADING` = jeton
  exact. Kill-switch = retirer la variable (testé).
- **RiskGuard** : taille/concentration de position, drawdown, perte quotidienne,
  circuit breaker. Le cap de concentration est aussi appliqué **en amont** de
  l'allocation (plafonnement + redistribution), pas seulement en rejet.
- **Coûts calibrés** Alpaca (`CostModel.alpaca_equities` : commission 0 + slippage
  2.5 bps, mesuré sur cotations réelles) — utilisés par toute la validation.

## Données (toutes point-in-time / fail-safe)

| Donnée | Source réelle | Loader | Repli |
|--------|---------------|--------|-------|
| Prix OHLCV ajustés | Alpaca (IEX) | `data/pit_loader`, `data/alpaca_history` | synthétique (interdictible) |
| Fondamentaux (filing dates) | Polygon | `data/fundamentals_pit_loader` (as-of) | synthétique / abstention |
| Appartenance univers (delistings) | Polygon | `data/pit_universe` (masque) | synthétique |
| Sentiment | FinBERT / news | `sentiment/…` | abstention si pas de données |

Anti-look-ahead **structurel** (jointures as-of sur les dates de dépôt).
Biais de survie **quantifié** : 36,8 % de l'univers US de 2020 a delisté en 6 ans.

## Observabilité (P4)

- **Journal** JSONL append-only (`trading/journal`) : chaque intention/résultat
  d'ordre + snapshots de compte.
- **Réconciliation** (`trading/reconciliation`) : journal ↔ broker à chaque run.
- **Suivi P&L** (`trading/pnl`, `scripts/pnl_report.py`) : equity, rendement, drawdown.
- **Alerting** fail-safe (`trading/alerts`) : écart de réconciliation → CRITICAL,
  échec de run → ERROR ; puits log + fichier + webhook.

## Hors chemin de production (recherche / expérimental)

`rl/`, `deep_learning/`, les moteurs de features redondants (`ml/`,
`ml_features*`, `features/`), `analysis/master_orchestrator` (neutralisé) et les
orphelins (`async_pipeline/`, `database/`) **ne participent pas à la décision** —
ils s'abstiennent ou ne sont pas câblés. Ils ne rejoignent la décision que via le
portail de validation, jamais par défaut.
