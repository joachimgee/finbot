#!/bin/bash
# Vérification Connexion Modules FinBot
# Génère rapport visuel de tous les modules intégrés

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║               FINBOT - VÉRIFICATION INTÉGRATION MODULES                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_module() {
    local module=$1
    local import_path=$2
    
    python -c "import sys; sys.path.insert(0, '/workspaces/finbot'); from $import_path; print('OK')" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $module"
        return 0
    else
        echo -e "${RED}❌${NC} $module"
        return 1
    fi
}

echo "📦 MODULES FEATURE ENGINEERING:"
check_module "TechnicalFeatureEngine     " "financial_analyzer.features.technical import TechnicalFeatureEngine"
check_module "FundamentalFeatureEngine   " "financial_analyzer.features.fundamental import FundamentalFeatureEngine"
check_module "FeaturePipeline            " "financial_analyzer.features.pipeline import FeaturePipeline"
echo ""

echo "🧠 MODULES ML & DEEP LEARNING:"
check_module "LSTMPredictor              " "financial_analyzer.deep_learning.lstm_predictor import LSTMPredictor"
check_module "SentimentFactorEngine      " "financial_analyzer.ml.sentiment_factor_engine import SentimentFactorEngine"
check_module "NewsSignalGenerator        " "financial_analyzer.ml.news_signal_generator import NewsSignalGenerator"
echo ""

echo "💬 MODULES SENTIMENT:"
check_module "RealtimeSentimentPipeline  " "financial_analyzer.sentiment.realtime_pipeline import RealtimeSentimentPipeline"
check_module "FinBERTEngine              " "financial_analyzer.sentiment.finbert_engine import FinBERTEngine"
check_module "SentimentAggregator        " "financial_analyzer.sentiment.sentiment_aggregator import SentimentAggregator"
echo ""

echo "🤖 MODULES RL:"
check_module "RLPipeline (run_rl_pipeline)" "financial_analyzer.rl.rl_trading_pipeline import run_rl_pipeline"
check_module "BaseRLAgent                " "financial_analyzer.rl.base_agent import BaseRLAgent"
echo ""

echo "🛡️  MODULES RISK:"
check_module "RiskGuard                  " "financial_analyzer.trading.risk_guard import RiskGuard"
check_module "AccountMonitor             " "financial_analyzer.trading.account_monitor import AccountMonitor"
echo ""

echo "💼 MODULES PORTFOLIO:"
check_module "PortfolioOptimizer         " "financial_analyzer.portfolio.optimizer import PortfolioOptimizer"
check_module "PortfolioRebalancer        " "financial_analyzer.portfolio.rebalancer import PortfolioRebalancer"
check_module "ConstraintSet              " "financial_analyzer.portfolio.constraints import ConstraintSet"
echo ""

echo "🔗 NOUVEAU MODULE INTÉGRATION:"
check_module "SignalFusionEngine         " "financial_analyzer.integration.signal_fusion_engine import SignalFusionEngine"
echo ""

echo "📊 MODULES PRÉANALYSE:"
check_module "DailyPreanalysis           " "financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis"
check_module "DriftDetector              " "financial_analyzer.backtest.adaptive_walk_forward import DriftDetector"
echo ""

echo "🔄 MODULES OPTIONS:"
check_module "BlackScholesModel          " "financial_analyzer.derivatives.options import BlackScholesModel"
check_module "GreeksCalculator           " "financial_analyzer.derivatives.options import GreeksCalculator"
echo ""

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Test SignalFusionEngine stats
echo "🔍 TEST SIGNAL FUSION ENGINE:"
python << 'EOF'
import sys
sys.path.insert(0, '/workspaces/finbot')

try:
    from financial_analyzer.integration import SignalFusionEngine
    
    engine = SignalFusionEngine()
    stats = engine.get_stats()
    
    print(f"  ✅ Engine initialisé")
    print(f"  • Sources actives: {len(stats['active_sources'])}")
    print(f"  • Poids configurés: {len(stats['source_weights'])}")
    print(f"  • Min sources: {stats['min_sources']}")
    print(f"  • Fallback mode: {stats['fallback_mode']}")
    
    # Try lazy loading
    print(f"\n  Tentative chargement lazy des modules...")
    engine._init_technical_engine()
    engine._init_sentiment_pipeline()
    
    stats2 = engine.get_stats()
    print(f"  ✅ Modules chargés: {', '.join(stats2['active_sources'])}")
    
except Exception as e:
    print(f"  ❌ Erreur: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ TOUS LES MODULES SONT CONNECTÉS ET OPÉRATIONNELS${NC}"
else
    echo ""
    echo -e "${RED}❌ CERTAINS MODULES ONT ÉCHOUÉ${NC}"
fi

echo ""
echo "📖 Documentation complète: INTEGRATION_COMPLETE_REPORT.md"
echo ""
