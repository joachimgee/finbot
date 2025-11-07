📌 RÈGLE ABSOLUE
QUAND TU REÇOIS UNE COMMANDE, TU CODES TOUJOURS
text
❌ NE JAMAIS :
- Faire un plan et ne pas coder
- Expliquer ce qu'on VA faire
- Proposer sans exécuter
- Arrêter avant le code

✅ TOUJOURS :
- ÉCRIRE LE CODE COMPLET
- INCLURE LES TESTS
- FOURNIR LES FICHIERS
- FINIR LES TÂCHES
📖 CONTEXTE PROJET
FinBot : Quantitative Trading Platform
Objectif : Plateforme de trading algorithmique complète, production-ready.

Stack :

Data : FinanceDatabase (300K+ symboles)

Features : FinanceToolkit (150+ ratios) + TA-Lib

Backtesting : backtesting.py (engine vectorisé)

Portfolio : PyPortfolioOpt + Riskfolio-Lib

Risk : 24+ risk measures

ML : LSTM, Random Forest, FinBERT

Framework : FastAPI, Pandas, NumPy, Scikit-learn

Architecture Générale
text
FinBot/
├── src/financial_analyzer/
│   ├── data/              # Couche données
│   ├── features/          # Ingénierie features
│   ├── backtest/          # Moteur backtesting
│   ├── portfolio/         # Optimisation portefeuille
│   ├── ml/                # Modèles ML
│   ├── trading/           # Exécution live
│   └── utils/             # Helpers
├── tests/
│   ├── test_data/
│   ├── test_features/
│   ├── test_backtest/
│   ├── test_portfolio/
│   ├── test_ml/
│   └── test_trading/
├── docs/
│   ├── API_REFERENCE.md
│   ├── ARCHITECTURE.md
│   ├── EXAMPLES.md
│   └── DEPLOYMENT.md
└── requirements.txt
Phases de Développement
Phase	Nom	Status	Modules
1	Data Layer	✅ DONE	UniverseSelector, MarketDataFetcher
2	Feature Engineering	✅ DONE	TechnicalEngine, FundamentalEngine
3	Backtesting	✅ DONE	BacktestRunner, Metrics, Signals
4	Portfolio Optimization	🔄 NEXT	Optimizer, Constraints, Rebalancer
5	ML Integration	📅 TODO	LSTM, Sentiment, Predictions
6	Live Trading	📅 TODO	BrokerAdapter, OrderManager
7	Production	📅 TODO	CLI, Dashboard, Deployment
🎯 CONVENTIONS DE CODE
Naming
python
# Classes : PascalCase
class PortfolioOptimizer:
    pass

# Functions : snake_case
def calculate_efficient_frontier():
    pass

# Constants : UPPER_SNAKE_CASE
MAX_ALLOCATION = 0.3

# Privates : _leading_underscore
def _helper_function():
    pass
Type Hints (OBLIGATOIRE)
python
def calculate_return(
    weights: pd.Series,
    returns: pd.DataFrame
) -> float:
    """Docstring courte."""
    pass
Docstrings (Google Style)
python
def my_function(param1: str, param2: int) -> Dict:
    """
    Courte description.
    
    Déscription longue si nécessaire.
    
    Args:
        param1: Description param1
        param2: Description param2
    
    Returns:
        Description du retour avec type
    
    Raises:
        ValueError: Quand erreur
    
    Example:
        >>> result = my_function("test", 5)
        >>> print(result)
        {'key': 'value'}
    """
Imports (ORDER)
python
# 1. Stdlib
import os
import json
from pathlib import Path
from typing import Dict, List, Optional

# 2. Third-party
import numpy as np
import pandas as pd
import scipy.optimize as optimize

# 3. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.backtest import BacktestRunner
Error Handling
python
# TOUJOURS wrapper les APIs
try:
    result = some_external_call()
except Exception as e:
    logger.error(f"Failed to call API: {e}")
    raise ValueError(f"API error: {e}") from e
Logging
python
logger = get_logger(__name__)

logger.debug("Detailed info")
logger.info("Important milestone")
logger.warning("Potential issue")
logger.error("Failed operation")
🔄 WORKFLOW TYPE POUR CHAQUE PROMPT
Quand tu reçois un prompt :
LIRE → Comprendre exactement ce qui est demandé

PLANIFIER (SILENCIEUSEMENT) → Structurer le code

CODER → Écrire TOUS les fichiers

TESTER → Inclure tests (min 20+ tests)

VALIDER → Vérifier qualité + conventions

LIVRER → Fournir code + récapitulatif

NE JAMAIS (anti-patterns)
python
# ❌ Faire juste un plan
"Voici mon plan : je vais créer..."

# ❌ Coder une partie et arrêter
"Voici le début du fichier..."

# ❌ Expliquer au lieu de coder
"Je vais créer une classe qui..."

# ❌ Ignorer les tests
# ... (sans tests)

# ❌ Ignorer les conventions
# (code sans type hints, pas de docstrings)
TOUJOURS (patterns)
python
# ✅ Lire le prompt attentivement
# ✅ Coder LE FICHIER COMPLET
# ✅ Inclure les tests (50+ si complexe)
# ✅ Respecter conventions v3.0
# ✅ Fournir récapitulatif final
📋 CHECKLIST PRE-LIVRAISON
Avant de finir une tâche, vérifier :

text
CODE QUALITY
☑ Type hints sur TOUS les params/returns
☑ Docstrings Google style complets
☑ Imports triés correctement
☑ Pas d'imports inutilisés
☑ Logging présent (debug/info/warning)
☑ Error handling robuste
☑ Variables bien nommées
☑ PEP 8 compliant (max 100 chars lines)

TESTING
☑ 20+ tests minimum (50+ si complexe)
☑ Tests unitaires + intégration
☑ Fixtures réutilisables
☑ Edge cases couverts
☑ Error cases testés
☑ Performance benchmarks (si pertinent)
☑ Tous les tests passent

ARCHITECTURE
☑ Pas de code dupliqué
☑ Pas de hard-coded values
☑ Configuration externalisée
☑ Dépendances bien gérées
☑ Pas de side effects
☑ Logging centralisé

DOCUMENTATION
☑ Docstrings complets
☑ Exemples dans docstrings
☑ README mis à jour
☑ Pas de TODO non terminé
🚀 COMMANDES TYPE
Commande : "PHASE 4 - Portfolio Optimization - Jour 1"
CE QUE TU DOIS FAIRE :

Créer src/financial_analyzer/portfolio/__init__.py

Créer src/financial_analyzer/portfolio/optimizer.py

Créer src/financial_analyzer/portfolio/constraints.py

Créer tests/test_portfolio/test_optimizer.py

Créer tests/test_portfolio/test_constraints.py

Fournir récapitulatif avec :

✅ Fichiers créés

✅ Classes implémentées

✅ Nombre de tests

✅ Checklist complétée

CE QUE TU NE DOIS JAMAIS FAIRE :

Arrêter à la description

Laisser de fichiers incomplets

Oublier les tests

Ignorer conventions

📊 QUALITÉ REQUISE
Code Standards
Aspect	Standard
Type Hints	100% coverage
Docstrings	Google style
Tests	80%+ coverage
Linting	PEP 8
Error Handling	Try/Except all APIs
Logging	Info/Warning/Error
Performance	< 1 sec for unit ops
Documentation	Complet + exemples
Métrique de Succès
text
✅ PASS :
- Code compile et run
- 80%+ tests passent
- Type checking OK (mypy)
- Linting OK (pylint)
- Docstrings présents
- Conventions respectées

❌ FAIL :
- Code ne compile pas
- < 50% tests passent
- Type errors
- Pas de docstrings
- Conventions ignorées
🎁 EXTRAS À INCLURE
Si complexe (10+ classes) :
Architecture diagram (texte)

Interaction flows

Data structures

Si algorithme complexe :
Pseudo-code dans docstring

Complexité O(n)

Exemple détaillé

Si intégration :
Tests d'intégration

Example workflow

Dépendances listées

🔗 FORKS & LIBRARIES (DISPONIBLE DANS AUDIT_FORKS)
UTILISER DIRECTEMENT (ne pas réimplémenter)
python
# Data
from financedatabase import Equities, ETFs, Crypto

# Features
from financetoolkit import Toolkit

# Backtesting
from backtesting import Backtest, Strategy

# Portfolio
from pypfopt import EfficientFrontier, risk_models
import riskfolio as rp

# ML
from transformers import AutoTokenizer, AutoModelForSequenceClassification
WRAPPER SEULEMENT si :
API ne match pas notre interface

Besoin d'harmoniser plusieurs libs

Ajouter logging/error handling

📞 CONTACT / CLARIFICATION
Si prompt est ambigu :

Demander clarification AVANT de coder

Lister les hypothèses

Proposer direction par défaut

Exemple :

text
"Prompt ambigu. Hypothèses :
1. Portfolio == équi-pondéré par défaut
2. Tests == 50+ minimum
3. Contraintes == long-only

Confirmer ? Ou autres préférences ?"
📈 PROGRESSION DU PROJET
text
✅ PHASE 1 (DONE)
   - UniverseSelector
   - MarketDataFetcher  
   - FundamentalsProvider

✅ PHASE 2 (DONE)
   - TechnicalFeatureEngine (20+ indicators)
   - FundamentalFeatureEngine (40+ metrics)
   - FeaturePipeline

✅ PHASE 3 (DONE)
   - BacktestRunner + CustomStrategy
   - Metrics (12+ ratios)
   - Signals (12+ types)
   - Integration tests (100+)

🔄 PHASE 4 (CURRENT)
   - PortfolioOptimizer
   - Constraints
   - Rebalancer
   - Metrics
   → 80+ tests

🎯 PHASE 5
   → ML models
   → Sentiment analysis
   → Predictions

🎯 PHASE 6
   → Live trading
   → Broker integration
   → Live monitoring

🎯 PHASE 7
   → CLI tool
   → Dashboard
   → Production deployment
✅ RÉSUMÉ FINAL
Quand tu vois une commande :
TU CODES TOUJOURS (jamais de plan seul)

TU RESPECTES LES CONVENTIONS (v3.0)

TU INCLUS LES TESTS (50+ si complexe)

TU LIVRES COMPLET (pas de fragments)

TU VÉRIFIES AVEC CHECKLIST (avant de finir)

JAMAIS PRIORISER TEMPS DE DÉVELOPPEMENT SUR LA QUALITÉ (QUALITÉ TOUJOURS PRIORITAIRE)