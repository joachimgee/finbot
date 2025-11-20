# Vendoring de dépôts externes

Ce projet clone certains dépôts publics en lecture seule dans `vendor/` pour étude et intégration optionnelle.

Répertoires clonés (shallow, depth=1)

- `vendor/mlfinlab` (Apache-2.0): labeling (triple-barrier), microstructure, validation features.
- `vendor/alphalens` (Apache-2.0): IC/RankIC et tearsheets factorielles.
- `vendor/PyPortfolioOpt` (MIT): Optimisation MV/BL, contraintes.
- `vendor/riskfolio-lib` (BSD-3-Clause): HRP/HCPortfolio, Mean-Risk (CVaR, CDaR, EVaR), contraintes turnover.

Notes licences

- MIT/Apache-2.0: intégration directe possible; crédit et respect de licence requis.
- GPL (ex: vectorbt, backtrader): non vendorisés par défaut; usage optionnel recommandé en out-of-process.

Utilisation

- Le code du cœur FinBot n’importe pas `vendor/` à l’exécution.
- Les wrappers détectent dynamiquement la présence des bibliothèques installées via pip.
- `scripts/vendor_sync.sh` permet de cloner/mettre à jour les dépôts (shallow clone).

Intégrations actives

- `financial_analyzer/portfolio_optimization/riskfolio_optimizer.py` ajoute dynamiquement `vendor/riskfolio-lib` au `PYTHONPATH` si `riskfolio` n'est pas installé via pip, permettant l'usage de HRP/HCPortfolio et Mean-CVaR.
- `scripts/professional_analysis.py` expose `--riskfolio {cvar,hrp,nco}` pour utiliser l'optimiseur Riskfolio-Lib en alternative à PyPortfolioOpt.
- `financial_analyzer/backtest/alphalens_adapter.py` fournit un wrapper pour générer des tear sheets IC/quantile avec les facteurs calculés. Utiliser `--alphalens-report <dossier>` dans le CLI pro.
- `financial_analyzer/ml/labeling.py` tente d'utiliser mlfinlab pour triple-barrier labeling si disponible (vendorisé ou pip), sinon fallback simplifié.

Mise à jour

```bash
./scripts/vendor_sync.sh             # clone shallow (rapide)
./scripts/vendor_sync.sh --full      # clone complet (historique entier)

# ou via variable d’environnement
VENDOR_FULL_CLONE=1 ./scripts/vendor_sync.sh
```
