"""
Tests pour le module Fundamental Features.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.features.fundamental import FundamentalFeatureEngine


# Markers pytest pour tous les tests de ce fichier
pytestmark = [pytest.mark.features, pytest.mark.unit]


@pytest.fixture
def mock_quarterly_fundamentals():
    """
    Fixture avec 8 trimestres de ratios financiers réalistes.
    
    Simule une entreprise tech avec bonne croissance et profitabilité.
    """
    dates = pd.date_range('2022-Q1', periods=8, freq='Q')
    
    # Données réalistes avec tendances
    np.random.seed(42)
    
    # Croissance progressive
    revenue = np.array([1000, 1050, 1100, 1180, 1250, 1320, 1400, 1480])
    net_income = revenue * 0.20  # Marge nette 20%
    total_assets = revenue * 2.5
    equity = total_assets * 0.6
    total_debt = total_assets * 0.3
    
    return pd.DataFrame(
        {
            # Ratios de valuation
            'PE': [25.0, 24.5, 26.0, 27.5, 26.5, 25.5, 24.0, 23.5],
            'PB': [5.0, 5.1, 5.2, 5.4, 5.3, 5.2, 5.0, 4.9],
            'PS': [8.0, 7.8, 8.2, 8.5, 8.3, 8.0, 7.7, 7.5],
            
            # Ratios de rentabilité
            'ROE': [18.0, 18.5, 19.0, 19.5, 19.2, 18.8, 18.5, 18.2],
            'ROA': [10.5, 10.8, 11.0, 11.3, 11.1, 10.9, 10.7, 10.5],
            
            # Financials
            'Revenue': revenue,
            'NetIncome': net_income,
            'TotalAssets': total_assets,
            'Equity': equity,
            'TotalDebt': total_debt,
            'FreeCashFlow': net_income * 0.8,  # FCF = 80% de NetIncome
            
            # Ratios additionnels
            'DebtToEquity': total_debt / equity,
            'CurrentRatio': [1.8, 1.9, 2.0, 2.1, 2.0, 1.9, 1.8, 1.7],
            'GrossMargin': [60.0, 61.0, 62.0, 62.5, 62.0, 61.5, 61.0, 60.5],
            'OperatingMargin': [25.0, 25.5, 26.0, 26.5, 26.0, 25.5, 25.0, 24.5],
            'NetMargin': [20.0, 20.2, 20.5, 20.8, 20.5, 20.2, 20.0, 19.8],
            
            # Pour efficience
            'AccountsReceivable': revenue * 0.15,
            
            # Pour interest coverage
            'EBIT': net_income * 1.5,
            'InterestExpense': total_debt * 0.03,  # 3% taux d'intérêt
        },
        index=dates,
    )


@pytest.fixture
def mock_minimal_fundamentals():
    """Fixture avec ratios minimaux seulement."""
    dates = pd.date_range('2023-Q1', periods=4, freq='Q')
    
    return pd.DataFrame(
        {
            'PE': [20.0, 22.0, 24.0, 23.0],
            'PB': [3.0, 3.2, 3.4, 3.3],
            'ROE': [15.0, 16.0, 17.0, 16.5],
            'ROA': [8.0, 8.5, 9.0, 8.8],
        },
        index=dates,
    )


class TestFundamentalFeatureEngineInit:
    """Tests d'initialisation du FundamentalFeatureEngine."""
    
    @pytest.mark.unit
    def test_init_valid_fundamentals(self, mock_quarterly_fundamentals):
        """Test initialisation avec fundamentals valides."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals, historical_periods=4)
        
        assert engine.df is not None
        assert len(engine.df) == 8
        assert engine.historical_periods == 4
        assert 'PE' in engine.df.columns
        assert 'ROE' in engine.df.columns
    
    @pytest.mark.unit
    def test_init_empty_dataframe(self):
        """Test ValueError si DataFrame vide."""
        empty_df = pd.DataFrame()
        
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            FundamentalFeatureEngine(empty_df)
    
    @pytest.mark.unit
    def test_init_none_dataframe(self):
        """Test ValueError si DataFrame = None."""
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            FundamentalFeatureEngine(None)
    
    @pytest.mark.unit
    def test_init_insufficient_data_warning(self):
        """Test que initialisation OK avec peu de données (warning attendu)."""
        short_df = pd.DataFrame(
            {'PE': [20.0, 22.0], 'PB': [3.0, 3.2], 'ROE': [15.0, 16.0], 'ROA': [8.0, 8.5]},
            index=pd.date_range('2023-Q1', periods=2, freq='Q'),
        )
        
        # Doit fonctionner mais avec warnings
        engine = FundamentalFeatureEngine(short_df, historical_periods=4)
        assert len(engine.df) == 2
    
    @pytest.mark.unit
    def test_init_invalid_historical_periods(self, mock_minimal_fundamentals):
        """Test ValueError si historical_periods <= 0."""
        with pytest.raises(ValueError, match="historical_periods doit être > 0"):
            FundamentalFeatureEngine(mock_minimal_fundamentals, historical_periods=0)
        
        with pytest.raises(ValueError, match="historical_periods doit être > 0"):
            FundamentalFeatureEngine(mock_minimal_fundamentals, historical_periods=-1)


class TestGrowthFeatures:
    """Tests de calcul des features de croissance."""
    
    @pytest.mark.unit
    def test_growth_qoq_calculation(self, mock_quarterly_fundamentals):
        """Test calcul croissance QoQ."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        growth = engine.calculate_growth_features()
        
        assert isinstance(growth, pd.DataFrame)
        assert len(growth) == 8
        # Devrait contenir Revenue_QoQ_Growth
        assert 'Revenue_QoQ_Growth' in growth.columns
    
    @pytest.mark.unit
    def test_growth_first_period_nan(self, mock_quarterly_fundamentals):
        """Test que première période = NaN (pas de période précédente)."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        growth = engine.calculate_growth_features()
        
        # Première ligne doit être NaN pour toutes colonnes growth
        assert growth.iloc[0].isna().all()
    
    @pytest.mark.unit
    def test_growth_with_nan_handling(self):
        """Test gestion NaN dans données source."""
        df = pd.DataFrame(
            {
                'PE': [20, 22, 24, 23],
                'PB': [3, 3.2, 3.4, 3.3],
                'ROE': [15, 16, 17, 16.5],
                'ROA': [8, 8.5, 9, 8.8],
                'Revenue': [1000, np.nan, 1200, 1300],  # NaN au milieu
                'NetIncome': [100, 110, 120, 130],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        growth = engine.calculate_growth_features()
        
        # Croissance avec NaN doit être gérée
        assert 'NetIncome_QoQ_Growth' in growth.columns
        assert growth['NetIncome_QoQ_Growth'].iloc[1] > 0  # Q2 growth


class TestValuationFeatures:
    """Tests de calcul des features de valuation."""
    
    @pytest.mark.unit
    def test_valuation_pe_trend_expensive(self):
        """Test détection PE cher (expensive)."""
        # PE élevé
        df = pd.DataFrame(
            {
                'PE': [40.0, 42.0, 45.0, 43.0],  # Élevé
                'PB': [5.0, 5.2, 5.4, 5.3],
                'ROE': [15.0, 16.0, 17.0, 16.5],
                'ROA': [8.0, 8.5, 9.0, 8.8],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        valuation = engine.calculate_valuation_features()
        
        assert 'PE_Trend' in valuation.columns
        # Au moins une période devrait être "Expensive"
        assert 'Expensive' in valuation['PE_Trend'].values
    
    @pytest.mark.unit
    def test_valuation_pe_trend_cheap(self):
        """Test détection PE bon marché (cheap)."""
        # PE bas
        df = pd.DataFrame(
            {
                'PE': [10.0, 9.0, 8.5, 9.5],  # Bas
                'PB': [1.5, 1.4, 1.3, 1.4],
                'ROE': [15.0, 16.0, 17.0, 16.5],
                'ROA': [8.0, 8.5, 9.0, 8.8],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        valuation = engine.calculate_valuation_features()
        
        assert 'PE_Trend' in valuation.columns
        # Au moins une période devrait être "Cheap"
        assert 'Cheap' in valuation['PE_Trend'].values
    
    @pytest.mark.unit
    def test_valuation_score_range(self, mock_quarterly_fundamentals):
        """Test que Valuation_Score est entre 0 et 100."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        valuation = engine.calculate_valuation_features()
        
        assert 'Valuation_Score' in valuation.columns
        scores = valuation['Valuation_Score'].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()
    
    @pytest.mark.unit
    def test_peg_ratio_calculation(self, mock_quarterly_fundamentals):
        """Test calcul PEG Ratio."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        valuation = engine.calculate_valuation_features()
        
        # PEG devrait être présent
        assert 'PEG_Ratio' in valuation.columns
    
    @pytest.mark.unit
    def test_peg_with_zero_growth(self):
        """Test que PEG = NaN si croissance = 0 (éviter division par zéro)."""
        df = pd.DataFrame(
            {
                'PE': [20.0, 20.0, 20.0, 20.0],
                'PB': [3.0, 3.0, 3.0, 3.0],
                'ROE': [15.0, 15.0, 15.0, 15.0],
                'ROA': [8.0, 8.0, 8.0, 8.0],
                'NetIncome': [100, 100, 100, 100],  # Pas de croissance
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        valuation = engine.calculate_valuation_features()
        
        # PEG devrait gérer division par zéro
        peg = valuation['PEG_Ratio']
        # PEG devrait être NaN ou géré (pas inf)
        assert not (peg == np.inf).any(), "PEG contains inf values"
        assert not (peg == -np.inf).any(), "PEG contains -inf values"


class TestQualityFeatures:
    """Tests de calcul des features de qualité."""
    
    @pytest.mark.unit
    def test_roe_quality_excellent(self):
        """Test ROE_Quality = 'Excellent' si ROE > 15%."""
        df = pd.DataFrame(
            {
                'PE': [20.0, 22.0, 24.0, 23.0],
                'PB': [3.0, 3.2, 3.4, 3.3],
                'ROE': [18.0, 19.0, 20.0, 19.5],  # Excellent (>15%)
                'ROA': [10.0, 10.5, 11.0, 10.8],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        quality = engine.calculate_quality_features()
        
        assert 'ROE_Quality' in quality.columns
        # Toutes périodes devraient être "Excellent"
        assert (quality['ROE_Quality'] == 'Excellent').all()
    
    @pytest.mark.unit
    def test_roe_quality_poor(self):
        """Test ROE_Quality = 'Poor' si ROE < 10%."""
        df = pd.DataFrame(
            {
                'PE': [20.0, 22.0, 24.0, 23.0],
                'PB': [3.0, 3.2, 3.4, 3.3],
                'ROE': [5.0, 6.0, 7.0, 6.5],  # Poor (<10%)
                'ROA': [3.0, 3.5, 4.0, 3.8],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        quality = engine.calculate_quality_features()
        
        assert 'ROE_Quality' in quality.columns
        # Toutes périodes devraient être "Poor"
        assert (quality['ROE_Quality'] == 'Poor').all()
    
    @pytest.mark.unit
    def test_debt_equity_assessment(self, mock_quarterly_fundamentals):
        """Test Leverage_Rating basé sur Debt/Equity."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        quality = engine.calculate_quality_features()
        
        assert 'Leverage_Rating' in quality.columns
        # Scores doivent être valides
        scores = quality['Leverage_Rating'].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()
    
    @pytest.mark.unit
    def test_liquidity_rating(self, mock_quarterly_fundamentals):
        """Test Liquidity_Rating basé sur Current Ratio."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        quality = engine.calculate_quality_features()
        
        assert 'Liquidity_Rating' in quality.columns
        # Scores doivent être valides
        scores = quality['Liquidity_Rating'].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()
    
    @pytest.mark.unit
    def test_quality_score(self, mock_quarterly_fundamentals):
        """Test Quality_Score (score global)."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        quality = engine.calculate_quality_features()
        
        assert 'Quality_Score' in quality.columns
        scores = quality['Quality_Score'].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()


class TestProfitabilityFeatures:
    """Tests de calcul des features de profitabilité."""
    
    @pytest.mark.unit
    def test_gross_margin_trend(self, mock_quarterly_fundamentals):
        """Test calcul Gross_Margin_Trend."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        profitability = engine.calculate_profitability_features()
        
        assert 'Gross_Margin_Trend' in profitability.columns
        # Première période = NaN
        assert pd.isna(profitability['Gross_Margin_Trend'].iloc[0])
    
    @pytest.mark.unit
    def test_net_margin_trend(self, mock_quarterly_fundamentals):
        """Test calcul Net_Margin_Trend."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        profitability = engine.calculate_profitability_features()
        
        assert 'Net_Margin_Trend' in profitability.columns
    
    @pytest.mark.unit
    def test_fcf_to_revenue_ratio(self, mock_quarterly_fundamentals):
        """Test calcul FCF/Revenue ratio."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        profitability = engine.calculate_profitability_features()
        
        assert 'FCF_to_Revenue' in profitability.columns
        # FCF/Revenue devrait être positif
        fcf_ratio = profitability['FCF_to_Revenue'].dropna()
        assert (fcf_ratio > 0).all()


class TestEfficiencyFeatures:
    """Tests de calcul des features d'efficience."""
    
    @pytest.mark.unit
    def test_asset_turnover(self, mock_quarterly_fundamentals):
        """Test calcul Asset Turnover."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        efficiency = engine.calculate_efficiency_features()
        
        assert 'Asset_Turnover' in efficiency.columns
        # Asset Turnover devrait être positif
        turnover = efficiency['Asset_Turnover'].dropna()
        assert (turnover > 0).all()
    
    @pytest.mark.unit
    def test_operating_efficiency_score(self, mock_quarterly_fundamentals):
        """Test Operating_Efficiency_Score."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        efficiency = engine.calculate_efficiency_features()
        
        assert 'Operating_Efficiency_Score' in efficiency.columns
        scores = efficiency['Operating_Efficiency_Score'].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()
    
    @pytest.mark.unit
    def test_dso_calculation(self, mock_quarterly_fundamentals):
        """Test calcul DSO (Days Sales Outstanding)."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        efficiency = engine.calculate_efficiency_features()
        
        assert 'DSO' in efficiency.columns
        # DSO devrait être raisonnable (< 365 jours)
        dso = efficiency['DSO'].dropna()
        assert (dso > 0).all()
        assert (dso < 365).all()  # Moins d'un an


class TestCalculateAllFeatures:
    """Tests de calcul de toutes les features."""
    
    @pytest.mark.unit
    def test_calculate_all_features_shape(self, mock_quarterly_fundamentals):
        """Test que calculate_all_features retourne toutes colonnes."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        features = engine.calculate_all_features()
        
        assert isinstance(features, pd.DataFrame)
        assert len(features) == 8  # 8 trimestres
        # Devrait avoir beaucoup de colonnes (≥35)
        assert len(features.columns) >= 35
    
    @pytest.mark.unit
    def test_all_features_columns(self, mock_quarterly_fundamentals):
        """Test présence colonnes clés."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        features = engine.calculate_all_features()
        
        # Vérifier colonnes critiques
        expected_cols = [
            'PE', 'PB', 'ROE', 'ROA',  # Original
            'Revenue_QoQ_Growth',  # Growth
            'PE_Trend', 'Valuation_Score',  # Valuation
            'ROE_Quality', 'Quality_Score',  # Quality
            'FCF_to_Revenue',  # Profitability
            'Asset_Turnover',  # Efficiency
        ]
        
        for col in expected_cols:
            assert col in features.columns, f"Colonne manquante: {col}"
    
    @pytest.mark.unit
    def test_all_features_no_negative_scores(self, mock_quarterly_fundamentals):
        """Test que tous les scores sont >= 0."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        features = engine.calculate_all_features()
        
        # Identifier colonnes score
        score_cols = [col for col in features.columns if 'Score' in col or 'Rating' in col]
        
        for col in score_cols:
            scores = features[col].dropna()
            if len(scores) > 0:
                assert (scores >= 0).all(), f"Colonne {col} contient scores négatifs"
                assert (scores <= 100).all(), f"Colonne {col} contient scores > 100"
    
    @pytest.mark.unit
    def test_all_features_index_preserved(self, mock_quarterly_fundamentals):
        """Test que l'index est préservé."""
        engine = FundamentalFeatureEngine(mock_quarterly_fundamentals)
        features = engine.calculate_all_features()
        
        # Index doit être identique
        pd.testing.assert_index_equal(features.index, mock_quarterly_fundamentals.index)
    
    @pytest.mark.unit
    def test_all_features_minimal_data(self, mock_minimal_fundamentals):
        """Test avec données minimales."""
        engine = FundamentalFeatureEngine(mock_minimal_fundamentals)
        features = engine.calculate_all_features()
        
        # Devrait fonctionner même avec colonnes limitées
        assert len(features) == 4
        assert 'PE' in features.columns
        assert 'ROE_Quality' in features.columns


class TestScoreFeatureHelper:
    """Tests de la méthode helper _score_feature."""
    
    @pytest.mark.unit
    def test_score_feature_range(self):
        """Test que _score_feature retourne scores 0-100."""
        df = pd.DataFrame(
            {'PE': [20, 22, 24, 23], 'PB': [3, 3.2, 3.4, 3.3], 'ROE': [15, 16, 17, 16.5], 'ROA': [8, 8.5, 9, 8.8]},
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        values = pd.Series([10, 20, 30, 40, 50])
        
        scores = engine._score_feature(values, lower_is_better=False)
        
        assert (scores >= 0).all()
        assert (scores <= 100).all()
    
    @pytest.mark.unit
    def test_score_feature_lower_is_better(self):
        """Test _score_feature avec lower_is_better=True."""
        df = pd.DataFrame(
            {'PE': [20, 22, 24, 23], 'PB': [3, 3.2, 3.4, 3.3], 'ROE': [15, 16, 17, 16.5], 'ROA': [8, 8.5, 9, 8.8]},
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        # PE: valeurs basses = mieux
        pe_values = pd.Series([10, 20, 30])
        scores = engine._score_feature(pe_values, lower_is_better=True)
        
        # Score le plus élevé devrait être pour valeur la plus basse (10)
        assert scores.iloc[0] > scores.iloc[2]
    
    @pytest.mark.unit
    def test_score_feature_higher_is_better(self):
        """Test _score_feature avec lower_is_better=False."""
        df = pd.DataFrame(
            {'PE': [20, 22, 24, 23], 'PB': [3, 3.2, 3.4, 3.3], 'ROE': [15, 16, 17, 16.5], 'ROA': [8, 8.5, 9, 8.8]},
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        # ROE: valeurs hautes = mieux
        roe_values = pd.Series([10, 20, 30])
        scores = engine._score_feature(roe_values, lower_is_better=False)
        
        # Score le plus élevé devrait être pour valeur la plus haute (30)
        assert scores.iloc[2] > scores.iloc[0]
    
    @pytest.mark.unit
    def test_score_feature_all_nan(self):
        """Test _score_feature avec toutes valeurs NaN."""
        df = pd.DataFrame(
            {'PE': [20, 22, 24, 23], 'PB': [3, 3.2, 3.4, 3.3], 'ROE': [15, 16, 17, 16.5], 'ROA': [8, 8.5, 9, 8.8]},
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(df)
        nan_values = pd.Series([np.nan, np.nan, np.nan])
        scores = engine._score_feature(nan_values)
        
        # Devrait retourner scores neutres (50)
        assert (scores == 50.0).all()


class TestEdgeCases:
    """Tests de cas limites."""
    
    @pytest.mark.unit
    def test_single_period(self):
        """Test avec une seule période (croissance impossible)."""
        single_period = pd.DataFrame(
            {'PE': [20.0], 'PB': [3.0], 'ROE': [15.0], 'ROA': [8.0]},
            index=pd.date_range('2023-Q1', periods=1, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(single_period)
        features = engine.calculate_all_features()
        
        # Devrait fonctionner mais growth = NaN
        assert len(features) == 1
        growth_cols = [col for col in features.columns if 'Growth' in col]
        for col in growth_cols:
            assert pd.isna(features[col].iloc[0])
    
    @pytest.mark.unit
    def test_missing_optional_columns(self):
        """Test avec colonnes optionnelles manquantes."""
        minimal = pd.DataFrame(
            {'PE': [20, 22, 24, 23], 'PB': [3, 3.2, 3.4, 3.3], 'ROE': [15, 16, 17, 16.5], 'ROA': [8, 8.5, 9, 8.8]},
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(minimal)
        features = engine.calculate_all_features()
        
        # Devrait fonctionner avec features limitées
        assert len(features) > 0
        assert 'PE' in features.columns
    
    @pytest.mark.unit
    def test_constant_values(self):
        """Test avec valeurs constantes (pas de variabilité)."""
        constant = pd.DataFrame(
            {
                'PE': [20.0, 20.0, 20.0, 20.0],
                'PB': [3.0, 3.0, 3.0, 3.0],
                'ROE': [15.0, 15.0, 15.0, 15.0],
                'ROA': [8.0, 8.0, 8.0, 8.0],
            },
            index=pd.date_range('2023-Q1', periods=4, freq='Q'),
        )
        
        engine = FundamentalFeatureEngine(constant)
        features = engine.calculate_all_features()
        
        # Growth devrait être 0
        growth_cols = [col for col in features.columns if 'Growth' in col]
        for col in growth_cols:
            growth_values = features[col].dropna()
            if len(growth_values) > 0:
                assert (growth_values == 0.0).all()
