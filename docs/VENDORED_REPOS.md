# Repos tiers vendorés (retirés du repo)

Le dossier `docs/Forks complet/` (~585 Mo) contenait des copies complètes de
repos open-source publics, et `vendor/` / `external_repos/` contenaient des
entrées de submodules vides. Tout a été retiré du suivi git pour alléger le
repo (1,3 Go → ~30 Mo). Ces projets s'installent via pip (`requirements.txt`)
ou se re-téléchargent depuis leurs sources :

| Projet | Source upstream | Installation |
|---|---|---|
| FinanceDatabase | https://github.com/JerBouma/FinanceDatabase | `pip install financedatabase` |
| FinanceToolkit | https://github.com/JerBouma/FinanceToolkit | `pip install financetoolkit` |
| PyPortfolioOpt | https://github.com/robertmartin8/PyPortfolioOpt | `pip install PyPortfolioOpt` |
| Riskfolio-Lib | https://github.com/dcajasn/Riskfolio-Lib | `pip install riskfolio-lib` |
| backtesting.py | https://github.com/kernc/backtesting.py | `pip install backtesting` |
| Finance | https://github.com/shashankvemuri/Finance | référence uniquement |
| financial-machine-learning | https://github.com/firmai/financial-machine-learning | référence uniquement |
| machine-learning-for-trading | https://github.com/stefan-jansen/machine-learning-for-trading | référence uniquement |
| alpaca-api | https://github.com/alpacahq/alpaca-trade-api-python | `pip install alpaca-trade-api` |
| FinRL | https://github.com/AI4Finance-Foundation/FinRL | `pip install finrl` |
| TensorTrade | https://github.com/tensortrade-org/tensortrade | `pip install tensortrade` |
| vectorbt | https://github.com/polakowo/vectorbt | `pip install vectorbt` |

## Fallback `vendor/`

Certains modules (`portfolio_optimization/riskfolio_optimizer.py`,
`portfolio/discrete_allocation.py`, `ml/cross_validation.py`, `ml/labeling.py`)
ajoutent `vendor/<lib>` au `sys.path` **uniquement si** le paquet pip n'est pas
installé. Ce mécanisme reste fonctionnel : pour l'utiliser, clonez la lib
concernée dans `vendor/` (dossier ignoré par git). Dans le cas normal
(dépendances installées via `requirements.txt`), il ne se passe rien.
