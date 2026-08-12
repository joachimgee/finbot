# Runbook — Passage paper → live (P4)

> **Principe fail-safe** : le système est en **paper par défaut**. Le live n'est
> possible qu'après un **double verrou** explicite. En cas de doute, ne pas activer.

Ce runbook définit (1) les critères chiffrés de passage, (2) la procédure
d'activation, (3) le **kill-switch** d'arrêt d'urgence, (4) la conduite en incident.
Tous les mécanismes cités sont réels et testés (références en fin de document).

---

## 0. Le double verrou (comment le live est protégé)

Aller en live exige **deux** conditions indépendantes, chacune insuffisante seule :

1. **Code/config** — l'adaptateur doit être construit en mode live
   (`AlpacaAdapter.from_env(mode='live')`). Le daemon est aujourd'hui **câblé en
   `mode='paper'`** (4 endroits) : passer en live est un changement de code/config
   délibéré, pas un accident d'exécution.
2. **Environnement** — `FINBOT_ENABLE_LIVE_TRADING` doit valoir **exactement**
   `I_UNDERSTAND_LIVE_TRADING_RISKS`. Toute autre valeur (absente, vide, `true`,
   `1`, faute de frappe, mauvaise casse) → **rétrogradé en paper**.

Sans **les deux**, `OrderGateway.submit` refuse toute soumission live
(`LiveTradingNotEnabledError`) au dernier moment, avant tout appel broker.

---

## 1. Critères chiffrés de passage (go-live gates)

Ne passer en live **que si TOUS** les critères sont remplis :

| # | Critère | Seuil | Vérification |
|---|---------|-------|--------------|
| 1 | Runs paper consécutifs **sans écart de réconciliation** | ≥ **20** | `logs/execution_journal_*.jsonl` : chaque run `réconciliation OK` |
| 2 | Suivi P&L exploitable | courbe produite, **drawdown paper > −10 %** | `python scripts/pnl_report.py` |
| 3 | Signaux = **registre validé uniquement** | `VALIDATED_SIGNALS` (aujourd'hui `momentum_12_1`) | portail `IC t > 2 ET Sharpe net > 0` en place |
| 4 | Chokepoint unique confirmé | **0** appel `submit_order` hors gateway | `pytest tests/test_scripts/test_daemon_safety_invariants.py` |
| 5 | RiskGuard configuré | limites position/concentration/drawdown/perte quotidienne + circuit breaker actifs | config du daemon (étape 10) |
| 6 | Cadence de rééquilibrage active | `rebalance_every=10` (config validée) | `RebalanceGate` + `logs/rebalance_state.json` |
| 7 | Alerting opérationnel | **alerte de test reçue** sur le canal | `FINBOT_ALERT_WEBHOOK` défini + 1 alerte test |
| 8 | Kill-switch testé | cycle activer→refuser vert | `pytest tests/test_trading/test_kill_switch.py` |
| 9 | Coûts calibrés | modèle Alpaca (`commission 0 + slippage 2.5 bps`) | `CostModel.alpaca_equities()` |
| 10 | Capital initial **modeste** défini | montant explicite, tolérance de perte assumée | décision opérateur |

> Rappel honnête : à ce jour, **un seul** signal a passé le portail
> (`momentum_12_1`). Les facteurs value/quality n'ont **pas** d'edge validé sur
> l'univers testé (cf. assessment P2). Ne pas trader de signal non enregistré.

---

## 2. Procédure d'activation

À faire **dans l'ordre**, sur un capital modeste :

1. Rejouer une validation paper de bout en bout, verte :
   ```bash
   python scripts/validate_paper_pipeline_alpaca.py          # dry-run
   python scripts/validate_paper_pipeline_alpaca.py --execute # ordres paper réels
   python scripts/pnl_report.py                               # P&L à jour
   ```
2. Configurer l'alerting : `export FINBOT_ALERT_WEBHOOK="https://<hook>"` et émettre
   une alerte de test (vérifier la réception).
3. **Verrou 1 (code/config)** : basculer le daemon en `mode='live'`
   (`AlpacaAdapter.from_env(mode='live')`). Revue par une 2e personne recommandée.
4. **Verrou 2 (env)** : activer le jeton **juste avant** le lancement :
   ```bash
   export FINBOT_ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISKS
   ```
5. Lancer un **premier run live à capital minimal**, surveiller la réconciliation
   et le P&L du run. Toute anomalie → **kill-switch** (section 3).

---

## 3. Kill-switch — arrêt d'urgence

**Halte immédiate de toute nouvelle soumission live :**

```bash
unset FINBOT_ENABLE_LIVE_TRADING      # (ou lui donner toute autre valeur)
```

Effet : `live_trading_enabled()` repasse à `False` ; le prochain
`OrderGateway.submit` en mode live lève `LiveTradingNotEnabledError` **avant**
tout appel broker. Aucun nouvel ordre live ne part. *(Cycle vérifié par
`test_kill_switch_full_cycle`.)*

- **Portée** : le kill-switch bloque les **nouveaux** ordres. Il ne liquide pas
  les positions déjà ouvertes — si nécessaire, liquider manuellement chez le
  broker, ou lancer un run paper de fermeture.
- **Verrou complémentaire** : pour un arrêt durable, remettre aussi le daemon en
  `mode='paper'` (verrou 1) afin qu'un jeton résiduel ne puisse rien réactiver.

---

## 4. Conduite en incident

- **Écart de réconciliation** (ordre journalisé absent chez le broker, ou ordre
  broker absent du journal = contournement du chokepoint) → **alerte CRITICAL**
  émise automatiquement. Action : **kill-switch**, puis investiguer avec le
  journal + le rapport de réconciliation avant de reprendre.
- **Circuit breaker / perte quotidienne** déclenchés par le RiskGuard → le run
  échoue proprement (alerte ERROR). Ne pas relancer sans comprendre la cause.
- **Drawdown** au-delà du seuil toléré → kill-switch, réévaluer signal & sizing.

---

## Références (mécanismes réels et testés)

| Mécanisme | Module | Test |
|-----------|--------|------|
| Double verrou mode/env | `trading/safety.py` | `tests/trading/test_safety.py`, `tests/test_trading/test_kill_switch.py` |
| Chokepoint unique | `trading/order_gateway.py` | `tests/trading/test_order_gateway.py`, `tests/test_scripts/test_daemon_safety_invariants.py` |
| Réconciliation | `trading/reconciliation.py` | (daemon étape 10) |
| Suivi P&L | `trading/pnl.py`, `scripts/pnl_report.py` | `tests/test_trading/test_pnl.py` |
| Alerting | `trading/alerts.py` | `tests/test_trading/test_alerts.py` |
| Portail de validation | `backtest/validation_gate.py` | `tests/test_backtest/test_validation_gate.py` |
| Cadence rééquilibrage | `trading/rebalance_gate.py` | `tests/test_trading/test_rebalance_gate.py` |
| Coûts calibrés | `backtest/signal_evaluation.CostModel.alpaca_equities` | `tests/test_backtest/test_cost_calibration.py` |
