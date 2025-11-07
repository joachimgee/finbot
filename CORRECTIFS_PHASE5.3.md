# 🔧 CORRECTIFS PHASE 5.3 - PROMPT POUR COPILOT

**STATUS ACTUEL**: 66/66 tests passing (100%), Quality 9.7/10

**OBJECTIF**: Appliquer 3 améliorations cosmétiques → Quality 9.9/10

---

## CORRECTIF 1/3: Documentation Args dans NewsSignalGenerator.__init__

**Fichier**: `src/financial_analyzer/ml/news_signal_generator.py`

**Localisation**: Ligne ~170-180 (dans la docstring de `__init__`)

**Action**: REMPLACER la docstring Args par une version plus détaillée.

**CHERCHER**:
```python
Args:
    sentiment_factors: Sentiment factors (from SentimentFactorEngine)
    technical_factors: Technical factors (from AlphaFactorEngine)
    prices: Price series (close prices) with DatetimeIndex
```

**REMPLACER PAR**:
```python
Args:
    sentiment_factors: Sentiment factors from SentimentFactorEngine.
                       Accepts two formats:
                       1. Dict[str, SentimentFactorResult] (from compute_sentiment_factors())
                       2. pd.DataFrame (columns = factor names, rows = dates)
                       If dict provided, automatically converted to DataFrame.
    technical_factors: Technical factors from AlphaFactorEngine.
                       Accepts two formats:
                       1. Dict[str, FactorResult] (from compute_all_factors())
                       2. pd.DataFrame (columns = factor names, rows = dates)
                       If dict provided, automatically converted to DataFrame.
    prices: Price series (close prices) with DatetimeIndex
```

---

## CORRECTIF 2/3: Auto-adjust estimation_window dans EventStudyAnalyzer.__init__

**Fichier**: `src/financial_analyzer/ml/event_study_analyzer.py`

**Localisation**: Ligne ~150-165 (dans `__init__`, APRÈS validation event_dates)

**Action**: REMPLACER la validation stricte par un auto-ajustement avec warning.

**CHERCHER ET SUPPRIMER** ces lignes (~ligne 155-160):
```python
# Validate inputs
if len(self.returns) < estimation_window:
    raise ValueError(
        f"Insufficient data: need at least {estimation_window} days for estimation, "
        f"got {len(self.returns)} days"
    )
```

**REMPLACER PAR**:
```python
# Validate and auto-adjust estimation_window if needed
available_days = len(self.returns)
if available_days < estimation_window:
    logger.warning(
        f"Insufficient data for estimation_window={estimation_window} days. "
        f"Auto-adjusting to {available_days} days (all available historical data). "
        f"Note: Beta estimate may be less reliable with fewer observations."
    )
    self.estimation_window = available_days
else:
    self.estimation_window = estimation_window
```

**IMPORTANT**: S'assurer que la variable `self.estimation_window` est utilisée partout au lieu de `estimation_window` dans le reste du code.

**VÉRIFIER** que `_estimate_market_model()` utilise bien `self.estimation_window` :
```python
def _estimate_market_model(self) -> Tuple[float, float]:
    # ...
    # Use self.estimation_window (not estimation_window parameter)
    df = df.tail(self.estimation_window)
    # ...
```

---

## CORRECTIF 3/3: Ajouter commentaire explicatif sur strong signals

**Fichier**: `src/financial_analyzer/ml/news_signal_generator.py`

**Localisation**: Ligne ~300 (dans `generate_signals()`, AVANT `# Initialize all signals to 0`)

**Action**: AJOUTER un bloc de commentaire explicatif.

**CHERCHER** cette ligne:
```python
# Initialize all signals to 0 (hold)
signals['signal'] = 0
```

**AJOUTER CE BLOC AVANT** (avant "Initialize all signals to 0"):
```python
# ===================================================================
# SIGNAL GENERATION LOGIC
# ===================================================================
# Note on Strong Signals (2, -2):
# Default thresholds are intentionally conservative (high precision, low recall).
# This ensures strong signals are only generated when there is high confidence:
#   - Extreme sentiment (>0.8 or <0.2 on [0,1] scale with default threshold=0.3)
#   - Strong technical confirmation (score >0.6)
#   - High news attention (count >=5 articles in 5-day window)
# 
# To generate more strong signals, reduce thresholds in generate_signals() call:
#   generator.generate_signals(
#       sentiment_threshold=0.2,      # Less strict (default: 0.3)
#       technical_score_threshold=0.5, # Less strict (default: 0.6)
#       news_count_threshold=3         # Less strict (default: 5)
#   )
# ===================================================================

# Initialize all signals to 0 (hold)
signals['signal'] = 0
```

---

## ✅ VALIDATION APRÈS CORRECTIFS

**Commandes à exécuter** (tu dois les lancer après mes modifications):
```bash
cd /workspaces/finbot

# 1. Vérifier que les tests passent toujours
python -m pytest tests/test_ml/test_news_sentiment_integration.py -v --tb=short

# 2. Type checking (doit rester clean)
python -m mypy src/financial_analyzer/ml/news_signal_generator.py --ignore-missing-imports --no-error-summary
python -m mypy src/financial_analyzer/ml/event_study_analyzer.py --ignore-missing-imports --no-error-summary

# 3. Coverage (doit rester 85-92%)
pytest tests/test_ml/test_news_sentiment_integration.py --cov=financial_analyzer.ml --cov-report=term-missing
```

**Résultat attendu**:
- ✅ 66/66 tests passing (pas de régression)
- ✅ Mypy clean (0 errors)
- ✅ Coverage 85-92% (inchangé)
- ✅ Quality Score: **9.9/10** (up from 9.7/10)

---

## 🎯 CHECKLIST

Après avoir appliqué les 3 correctifs:

- [ ] Correctif 1: Documentation Args clarifiée
- [ ] Correctif 2: Auto-adjust estimation_window avec warning
- [ ] Correctif 3: Commentaire explicatif strong signals
- [ ] Tests: 66/66 passing
- [ ] Mypy: 0 errors
- [ ] Coverage: 85-92%

**Une fois tout validé, confirme-moi et je génère le commit message final.**

---

**FIN DES CORRECTIFS**
