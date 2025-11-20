# Alpaca Live & Paper Trading

Cette page explique comment configurer les identifiants Alpaca, instancier l'adapter, et exécuter la pipeline de trading en conditions réelles (paper/live).

## Prérequis
- Compte Alpaca (Paper ou Live)
- Clés API: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`
- Paquet Python: `alpaca-trade-api`

## Variables d'environnement
```bash
export APCA_API_KEY_ID="..."
export APCA_API_SECRET_KEY="..."
# Mode paper par défaut => https://paper-api.alpaca.markets
```

## Démarrage rapide (Python one-liner)
```bash
python - <<'PY'
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline

adapter = AlpacaAdapter.from_env(mode='paper')
adapter.connect()

pipeline = LiveTradingPipeline(
    broker_adapter=adapter,
    tickers=['AAPL','MSFT','NVDA','GOOGL','AMZN'],
    initial_capital=100000.0,
    strategy='factor_ensemble'
)

res = pipeline.run(force=True)
print(res)

adapter.disconnect()
PY
```

## Instanciation explicite
```python
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
adapter = AlpacaAdapter(api_key='KEY', secret_key='SECRET', mode='paper')
adapter.connect()
```

## Multi-symbol bars (scalabilité 1000+ tickers)
`AlpacaAdapter.get_bars_multi(symbols, start, end, timeframe='1D', chunk_size=50)` permet de récupérer les barres en batch avec gestion du rate limit. La pipeline utilise automatiquement cette voie si disponible, sinon bascule en requêtes unitaires.

## Recommandations Scalabilité
- Utiliser `get_bars_multi` avec un `chunk_size` entre 25 et 100 selon le débit.
- Activer un cache local des prix récents pour éviter des appels répétés.
- Planifier les exécutions en dehors des pics (si possible) et respecter les limites.

## Sécurité & Risques
- Toujours commencer en mode Paper.
- Configurer `RiskGuard` (drawdown, taille max position, etc.).
 - Surveiller les logs et les métriques (Prometheus/ELK si déployé).

