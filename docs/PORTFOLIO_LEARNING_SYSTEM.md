# 🧠 Portfolio Learning System

## Vue d'ensemble

Système d'apprentissage continu qui analyse **chaque matin** les performances du portfolio et **apprend de ses erreurs** pour ajuster automatiquement les paramètres de trading.

## Architecture

```
CHAQUE MATIN (09:30 ET) :

┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 0 : APPRENTISSAGE (Portfolio Learner)               │
├─────────────────────────────────────────────────────────────┤
│ 1. Récupère portfolio actuel                               │
│ 2. Récupère historique 30 jours                            │
│ 3. Calcule 10+ métriques professionnelles                  │
│ 4. Détecte patterns d'erreurs                              │
│ 5. Génère insights actionnables                            │
│ 6. Ajuste paramètres automatiquement                       │
│ 7. Décide : Procéder ou STOP                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
           ✅ SI OK : Procéder
           🛑 SI CRITIQUE : STOP trading
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 1 : ANALYSE 12K SYMBOLES                             │
├─────────────────────────────────────────────────────────────┤
│ Analyse professionnelle 12,000 symboles globaux            │
│ (avec paramètres ajustés par learner)                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 2 : GESTION PORTFOLIO                                │
├─────────────────────────────────────────────────────────────┤
│ Décisions HOLD/SELL/BUY avec paramètres optimisés          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 3 : STATUS FINAL                                     │
└─────────────────────────────────────────────────────────────┘
```

## Métriques Professionnelles Calculées

Le système utilise **10+ ratios académiques** issus de la recherche finance quantitative :

### 1. Sharpe Ratio (Sharpe 1966)
```
Sharpe = (R_p - R_f) / σ_p
```
- **Source** : Sharpe, W. F. (1966). "Mutual Fund Performance". *Journal of Business*.
- **Interprétation** :
  - < 0 : Pire que risk-free
  - 0-1 : Sous-optimal
  - **1-2 : Acceptable** ✅
  - **2+ : Excellent** ⭐
- **Action si < 1.0** : Réduire volatilité ou augmenter rendement

### 2. Sortino Ratio (Sortino 1994)
```
Sortino = (R_p - R_f) / DD (downside deviation)
```
- **Source** : Sortino, F. & Price, L. (1994). "Performance Measurement in a Downside Risk Framework"
- **Interprétation** :
  - < 1.0 : Downside risk élevé
  - **1.5+ : Acceptable** ✅
  - **2.5+ : Excellent** ⭐
- **Action si < 1.5** : Implémenter protection downside (stop-loss, puts)

### 3. Calmar Ratio (Young 1991)
```
Calmar = CAGR / Max Drawdown
```
- **Source** : Young, T. (1991). "Calmar Ratio: A Smoother Tool". *Futures Magazine*.
- **Interprétation** :
  - < 0.3 : Drawdowns excessifs
  - **0.5+ : Acceptable** ✅
  - **1.0+ : Excellent** ⭐
- **Action si < 0.5** : Réduire positions, augmenter seuil qualité

### 4. Information Ratio (Treynor-Black 1973)
```
IR = (R_p - R_b) / Tracking Error
```
- **Source** : Treynor, J. & Black, F. (1973). "How to Use Security Analysis to Improve Portfolio Selection"
- **Interprétation** :
  - < 0 : Sous-performance vs benchmark
  - **0.5+ : Alpha positif** ✅
  - **1.0+ : Alpha significatif** ⭐
- **Action si < 0.5** : Améliorer sélection d'actions

### 5. Omega Ratio (Keating-Shadwick 2002)
```
Omega = Sum(gains above threshold) / Sum(losses below threshold)
```
- **Source** : Keating, C. & Shadwick, W. (2002). "A Universal Performance Measure". *Finance Dev Centre*.
- **Interprétation** :
  - < 1.0 : Pertes > gains
  - **1.3+ : Acceptable** ✅
  - **2.0+ : Excellent** ⭐
- **Avantage** : Capture toute la distribution (pas seulement moyenne/variance)

### 6. Max Drawdown
```
Max DD = max(Running Max - Current Value) / Running Max
```
- **Seuils** :
  - < 10% : Faible risque
  - **10-15% : Modéré** ✅
  - **15-25% : Élevé** ⚠️
  - **> 25% : CRITIQUE** 🛑 STOP trading

### 7. VaR / CVaR (95%)
```
VaR(95%) = Percentile 5% des pertes
CVaR(95%) = Moyenne des pertes au-delà de VaR
```
- **VaR Seuils** :
  - < 2% : Risque quotidien faible
  - **2-3% : Modéré** ✅
  - **> 3% : Élevé** ⚠️

### 8. Herfindahl Index (Concentration)
```
H = Sum(w_i²)
```
- **Seuils** :
  - < 0.10 : Bien diversifié
  - **0.10-0.15 : Acceptable** ✅
  - **> 0.15 : Trop concentré** ⚠️

### 9. Win Rate & Profit Factor
```
Win Rate = Wins / Total Trades
Profit Factor = Sum(gains) / Sum(losses)
```
- **Win Rate Seuils** :
  - **45%+ : Acceptable** ✅
  - **55%+ : Bon** ⭐
- **Profit Factor Seuils** :
  - **1.3+ : Acceptable** ✅
  - **2.0+ : Excellent** ⭐

### 10. M² (Modigliani-Modigliani 1997)
```
M² = (R_p - R_f) * (σ_b / σ_p) + R_f - R_b
```
- **Source** : Modigliani, F. & Modigliani, L. (1997). "Risk-Adjusted Performance"
- **Interprétation** : Excess return ajusté au même risque que benchmark

## Détection des Erreurs

### Patterns Détectés

#### 1. Sharpe < 1.0 → Risque excessif
**Symptôme** : Volatilité trop élevée vs rendement  
**Cause** : Positions trop volatiles, pas assez de filtrage qualité  
**Action** :
- Augmenter `hold_threshold` de 0.0 → 0.2
- Réduire positions volatiles (high-beta stocks)
- Ajouter contrainte volatilité max

#### 2. Sortino < 1.5 → Downside risk élevé
**Symptôme** : Pertes asymétriques (grosses pertes, petits gains)  
**Cause** : Pas de protection downside  
**Action** :
- Implémenter stop-loss à 8-10%
- Ajouter put options pour hedging
- Réduire exposition pendant drawdowns

#### 3. Calmar < 0.5 → Drawdowns excessifs
**Symptôme** : Max DD > 15%, pas compensé par CAGR  
**Cause** : Pas de gestion drawdown  
**Action** :
- Réduire `max_positions` de 200 → 100
- Augmenter `hold_threshold` de 0.0 → 0.3
- Stop trading si DD > 20%

#### 4. Max DD > 15% → Risque critique
**Symptôme** : Perte cumulative > 15%  
**Cause** : Exposition excessive, pas de stop-loss  
**Action URGENTE** :
- Réduire `max_positions` de 200 → 50 (-75%)
- Réduire `max_investment` de $1000 → $500 (-50%)
- Review stratégie complète

#### 5. Concentration > 0.15 (Herfindahl)
**Symptôme** : Portfolio trop concentré sur peu de positions  
**Cause** : Manque de diversification  
**Action** :
- Augmenter `max_positions`
- Réduire `max_investment` par position
- Ajouter contrainte max_weight = 5%

#### 6. Win Rate < 45%
**Symptôme** : Trop de trades perdants  
**Cause** : Sélection défaillante  
**Action** :
- Augmenter `hold_threshold` drastiquement (0.0 → 0.4)
- Réduire nombre de trades (swing trading vs day trading)
- Améliorer filtres qualité

## Ajustement Automatique des Paramètres

### Learning Rate : 0.1 (10%)

Le système ajuste progressivement les paramètres avec un **learning rate de 10%** pour éviter les changements trop brusques :

```python
new_value = current + learning_rate * (target - current)
```

### Paramètres Ajustés

#### 1. max_positions
- **Range** : [50, 200]
- **Ajustement** :
  - Si Max DD > 15% : Réduire de 50%
  - Si Concentration > 0.15 : Augmenter de 20%
  - Si Sharpe > 2.0 : Maintenir

#### 2. hold_threshold
- **Range** : [0.0, 0.5]
- **Ajustement** :
  - Si Sharpe < 1.0 : +0.2 (filtrer davantage)
  - Si Win Rate < 45% : +0.3 (sélection plus stricte)
  - Si Sortino < 1.5 : +0.15

#### 3. max_investment
- **Range** : [$100, $2000]
- **Ajustement** :
  - Si VaR > 3% : Réduire de 30%
  - Si Max DD > 15% : Réduire de 50%
  - Si Calmar < 0.5 : Réduire de 20%

#### 4. rebalance_threshold
- **Range** : [0.05, 0.25]
- **Ajustement** :
  - Si Turnover élevé : Augmenter (réduire trades)
  - Si Drift élevé : Réduire (rebalancer plus souvent)

## Utilisation

### 1. Workflow Automatique (GitHub Actions)

Le learner s'exécute **automatiquement chaque matin** à 09:30 ET :

```yaml
# .github/workflows/daily_professional_analysis_global_12k.yml
- name: Run Daily Portfolio Management (avec Learning)
  run: |
    python scripts/run_daily_portfolio_management.py \
      --limit 12000 --max-positions 200 --max-investment 1000 \
      --execute --mode paper
```

### 2. Exécution Manuelle

```bash
# Avec learning automatique
python scripts/run_daily_portfolio_management.py \
  --limit 12000 --max-positions 200 --max-investment 1000 \
  --execute --mode paper

# Output:
# ================================================================================
# 🧠 ÉTAPE 0: APPRENTISSAGE MATINAL (PRÉ-ANALYSE)
# ================================================================================
#
# 📊 PORTFOLIO ACTUEL:
#   • Equity: $959.25
#   • Cash: $240.71
#   • Positions: 51
#   • P&L jour: +$4.12
#   • P&L total: -$40,040.75
#
# 📈 MÉTRIQUES PROFESSIONNELLES:
#   • Sharpe Ratio: 0.842
#   • Sortino Ratio: 1.234
#   • Calmar Ratio: 0.387
#   • Max Drawdown: 18.23%
#   • Rendement annualisé: +12.45%
#
# 💡 INSIGHTS (4):
#
#   🔴 HIGH PRIORITY (2):
#     • Sharpe Ratio faible (0.84 < 1.0)
#       → Action: Réduire volatilité ou augmenter rendement. Considérer: (1) Stop-loss...
#     • Max Drawdown excessif (18.2% > 15.0%)
#       → Action: URGENT: Réduire exposition. (1) Passer max_positions de 200 → 100...
#
#   🟡 MEDIUM PRIORITY (1):
#     • VaR(95%) élevé (3.45% > 3.0%)
#
#   🟢 SUCCESS (1):
#     • Diversification acceptable
#
# ⚙️  AJUSTEMENTS RECOMMANDÉS:
#   • max_positions: 150.00
#     → Appliqué: max_positions = 150
#   • hold_threshold: 0.20
#     → Appliqué: hold_threshold = 0.20
#   • max_investment: 700.00
#     → Appliqué: max_investment = $700.00
#
# ✅ Apprentissage terminé, procéder avec analyse
```

### 3. Test Isolé du Learner

```python
from src.financial_analyzer.learning.portfolio_learner import PortfolioLearner

learner = PortfolioLearner(mode='paper', lookback_days=30)
result = learner.analyze_morning_pre_analysis()

print(f"Should proceed: {result.should_proceed}")
print(f"Insights: {len(result.insights)}")
print(f"Adjustments: {result.parameter_adjustments}")
```

## Historique d'Apprentissage

Le système stocke **90 jours d'historique** dans `data/portfolio_learning_history.json` :

```json
[
  {
    "date": "2025-11-21T09:30:00",
    "equity": 959.25,
    "positions_count": 51,
    "day_pnl": 4.12,
    "metrics": {
      "sharpe_ratio": 0.842,
      "sortino_ratio": 1.234,
      "calmar_ratio": 0.387,
      "max_drawdown_pct": 18.23
    },
    "insights_count": 4,
    "high_priority_insights": 2,
    "adjustments": {
      "max_positions": 150.0,
      "hold_threshold": 0.20
    },
    "should_proceed": true
  }
]
```

## Critères de Blocage

Le système **STOP automatiquement** le trading si :

1. **Max Drawdown > 25%** → Catastrophique, protection capital
2. **3+ erreurs high priority** → Stratégie défaillante
3. **Equity < 50% initial** → Perte de 50%+ non acceptable

## Amélioration Continue

### Cycle d'Apprentissage

```
Jour 1 : Max DD = 18% → Ajuste max_positions 200 → 150
         ↓
Jour 2 : Max DD = 16% → Ajuste hold_threshold 0.0 → 0.15
         ↓
Jour 3 : Max DD = 13% → Amélioration, maintenir
         ↓
Jour 4 : Sharpe = 1.2 → Succès, stabiliser
         ↓
Jour 5+ : Monitoring continu
```

### Feedback Loop

1. **Matin** : Learner analyse → Ajuste paramètres
2. **Analyse** : 12K symboles avec paramètres optimisés
3. **Trading** : Décisions HOLD/SELL/BUY améliorées
4. **Soir** : Résultats stockés
5. **Lendemain matin** : Learner analyse résultats → Cycle continue

## Références Académiques

1. **Sharpe, W. F. (1966)**. "Mutual Fund Performance". *Journal of Business*, 39(1), 119-138.

2. **Sortino, F. & Price, L. (1994)**. "Performance Measurement in a Downside Risk Framework". *Journal of Investing*, 3(3), 59-64.

3. **Young, T. (1991)**. "Calmar Ratio: A Smoother Tool". *Futures Magazine*, October 1991.

4. **Treynor, J. & Black, F. (1973)**. "How to Use Security Analysis to Improve Portfolio Selection". *Journal of Business*, 46(1), 66-86.

5. **Keating, C. & Shadwick, W. (2002)**. "A Universal Performance Measure". *Journal of Performance Measurement*, 6(3), 59-84.

6. **Modigliani, F. & Modigliani, L. (1997)**. "Risk-Adjusted Performance". *Journal of Portfolio Management*, 23(2), 45-54.

7. **Jensen, M. (1968)**. "The Performance of Mutual Funds in the Period 1945-1964". *Journal of Finance*, 23(2), 389-416.

8. **Treynor, J. (1965)**. "How to Rate Management of Investment Funds". *Harvard Business Review*, 43(1), 63-75.

## Avantages du Système

✅ **Automatique** : Apprend sans intervention humaine  
✅ **Académique** : Utilise ratios professionnels validés  
✅ **Adaptatif** : Ajuste paramètres selon conditions  
✅ **Protecteur** : Bloque trading si conditions critiques  
✅ **Transparent** : Insights clairs et actionnables  
✅ **Historisé** : 90 jours de données pour analyse  

## Limitations Actuelles

⚠️ **Besoin historique** : Minimum 2 jours pour métriques  
⚠️ **Learning rate fixe** : 10% peut être trop conservateur  
⚠️ **Pas de ML avancé** : Ajustements basés sur règles (pas encore neural network)  
⚠️ **Dépendance API Alpaca** : Portfolio history limité sur Paper  

## Prochaines Évolutions

🔜 **ML Reinforcement Learning** : Apprendre optimisation paramètres via RL  
🔜 **Multi-timeframe** : Analyse journalière + hebdomadaire + mensuelle  
🔜 **Régime Detection** : Identifier bull/bear markets, ajuster stratégie  
🔜 **Ensemble Learning** : Combiner plusieurs learners (short-term + long-term)  
🔜 **Advanced Attribution** : Brinson-Fachler complet avec facteurs  

---

**Dernière mise à jour** : 21 novembre 2025  
**Version** : 1.0.0  
**Auteur** : FinBot Learning Team
