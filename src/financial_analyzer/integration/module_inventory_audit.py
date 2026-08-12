"""Module Inventory Audit

Fournit un audit rapide de la couverture des modules dans le workflow journalier.
Chaque module clé est vérifié via import léger ou existence de sous-module.

L'objectif est de s'assurer que TOUS les modules principaux de `financial_analyzer`
soient soit directement utilisés dans le script quotidien, soit accessibles et
intégrables sans erreur d'import. Si un module est absent de l'utilisation
directe, on fournit un motif justificatif générique (à affiner).
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict
from pathlib import Path
import pkgutil

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


CORE_MODULES = [
    'analysis.master_orchestrator',
    'preanalysis.daily_preanalysis',
    'integration.signal_fusion_engine',
    'integration.weighting_engine',
    'portfolio',
    'risk',
    'features.technical',
    'features.fundamental',
    'sentiment.realtime_pipeline',
    'ml.sentiment_factor_engine',
    'deep_learning.lstm_predictor',
    'rl.rl_trading_pipeline',
    'trading.alpaca_adapter',
    'universe',
]


def audit_modules(base_pkg: str = 'financial_analyzer') -> Dict[str, Dict[str, str]]:
    results = {}
    for mod in CORE_MODULES:
        full = f"{base_pkg}.{mod}" if not mod.startswith(base_pkg) else mod
        entry = {'status': 'unused', 'detail': 'Not imported in daily run'}
        try:
            import_module(full)
            entry['status'] = 'ok'
            entry['detail'] = 'Import success'
        except Exception as e:
            entry['status'] = 'error'
            entry['detail'] = str(e)
        results[mod] = entry
    return results


def format_audit(results: Dict[str, Dict[str, str]]) -> str:
    lines = ["📦 Module Inventory Audit"]
    for name, info in results.items():
        status = info['status']
        lines.append(f" - {name}: {status} ({info['detail']})")
    return '\n'.join(lines)


if __name__ == '__main__':
    audit = audit_modules()
    print(format_audit(audit))
