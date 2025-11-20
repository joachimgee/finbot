#!/usr/bin/env python3
"""
Audit de complétude des modules dans src/financial_analyzer.

Génère un rapport rapide sur la présence et l'invocabilité des moteurs clés:
- AlphaFactorEngine (100+ facteurs)
- FeatureEngineer (114 facteurs ML)
- TechnicalFeatureEngine (25+ indicateurs)
- FundamentalFeatureEngine (47+ ratios) via FinanceToolkit si API fournie
- SentimentFactorEngine (présence)
- MLPredictor (train/predict sur OHLCV synthétique)

Utilise des données OHLCV synthétiques pour tester les flux de calcul.
"""

from __future__ import annotations

import os
from typing import Dict
import numpy as np
import pandas as pd


def _make_synth_ohlcv(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(loc=0.0005, scale=0.02, size=n)
    price = 100 * np.exp(np.cumsum(rets))
    high = price * (1 + rng.normal(0.001, 0.005, size=n))
    low = price * (1 - rng.normal(0.001, 0.005, size=n))
    open_ = price * (1 + rng.normal(0.0, 0.003, size=n))
    volume = rng.integers(1e5, 2e6, size=n)
    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': price, 'volume': volume
    })
    df.index = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B')
    return df


def main() -> None:
    report: Dict[str, Dict[str, object]] = {}
    ohlcv = _make_synth_ohlcv()

    # AlphaFactorEngine
    try:
        from financial_analyzer.ml.feature_engineering import AlphaFactorEngine
        afe = AlphaFactorEngine(ohlcv)
        af = afe.compute_all_factors()
        report['AlphaFactorEngine'] = {
            'available': True,
            'factors_count': len(af),
            'sample_keys': list(af.keys())[:10],
        }
    except Exception as e:
        report['AlphaFactorEngine'] = {'available': False, 'error': str(e)}

    # FeatureEngineer (ML 114)
    try:
        from financial_analyzer.ml_features.feature_engineer import FeatureEngineer
        fe = FeatureEngineer(ohlcv['close'].rename('CLOSE'))
        df_feats, ic = fe.compute_all_factors()
        report['FeatureEngineer'] = {
            'available': True,
            'features_count': df_feats.shape[1],
            'ic_count': int(ic.shape[0]),
        }
    except Exception as e:
        report['FeatureEngineer'] = {'available': False, 'error': str(e)}

    # TechnicalFeatureEngine
    try:
        from financial_analyzer.features.technical import TechnicalFeatureEngine
        te = TechnicalFeatureEngine(ohlcv.rename(columns=str.upper))
        tech = te.calculate_all_features()
        report['TechnicalFeatureEngine'] = {
            'available': True,
            'columns': int(tech.shape[1]),
            'sample_cols': list(tech.columns[:10]),
        }
    except Exception as e:
        report['TechnicalFeatureEngine'] = {'available': False, 'error': str(e)}

    # FundamentalFeatureEngine (si API disponible)
    try:
        from financial_analyzer.data.fundamentals import FundamentalsProvider
        from financial_analyzer.features.fundamental import FundamentalFeatureEngine
        api_key = os.environ.get('FMP_API_KEY') or os.environ.get('FINANCIAL_MODELING_PREP_API_KEY')
        if api_key:
            provider = FundamentalsProvider(api_key=api_key)
            ratios = provider.get_all_ratios('AAPL', period='quarterly', limit=4)
            if not ratios.empty:
                ffe = FundamentalFeatureEngine(ratios, historical_periods=4)
                fdf = ffe.calculate_all_features()
                report['FundamentalFeatureEngine'] = {
                    'available': True,
                    'columns': int(fdf.shape[1]),
                }
            else:
                report['FundamentalFeatureEngine'] = {
                    'available': True,
                    'columns': 0,
                    'warning': 'Aucun ratio renvoyé (clé API valide?)'
                }
        else:
            report['FundamentalFeatureEngine'] = {
                'available': False,
                'error': 'API key manquante (FMP_API_KEY)'
            }
    except Exception as e:
        report['FundamentalFeatureEngine'] = {'available': False, 'error': str(e)}

    # SentimentFactorEngine (présence)
    try:
        from financial_analyzer.ml.sentiment_factor_engine import SentimentFactorEngine  # noqa: F401
        report['SentimentFactorEngine'] = {'available': True}
    except Exception as e:
        report['SentimentFactorEngine'] = {'available': False, 'error': str(e)}

    # MLPredictor
    try:
        from financial_analyzer.analysis.ml_predictor import MLPredictor
        mlp = MLPredictor()
        mlp.train(ohlcv.rename(columns=str.upper))
        pred = mlp.predict(ohlcv.rename(columns=str.upper))
        report['MLPredictor'] = {
            'available': True,
            'pred_len': int(len(pred)) if pred is not None else 0,
        }
    except Exception as e:
        report['MLPredictor'] = {'available': False, 'error': str(e)}

    # Stratégies (comptage fichiers)
    import os as _os
    strat_dir = '/workspaces/finbot/src/financial_analyzer/strategies'
    try:
        files = [f for f in _os.listdir(strat_dir) if f.endswith('.py') and f != '__init__.py']
        report['Strategies'] = {'count_py': len(files), 'files_sample': files[:10]}
    except Exception as e:
        report['Strategies'] = {'available': False, 'error': str(e)}

    # Affichage
    print("===== AUDIT SRC COMPLETENESS =====")
    for k, v in report.items():
        print(f"\n[{k}]")
        for kk, vv in v.items():
            print(f"  - {kk}: {vv}")


if __name__ == '__main__':
    main()
