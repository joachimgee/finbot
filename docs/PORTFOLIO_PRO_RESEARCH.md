# Pipelines et Pratiques Professionnelles (Banques / Hedge Funds)

Objectif: cartographier une architecture de bout en bout et les pratiques de weighting/vérification utilisées par les acteurs institutionnels pour du multi-factor / ML sur univers large (1k–10k tickers).

## Architecture de Référence

- Ingestion & Univers
  - Data vendors multiples (QA: redondance, SLA, champs comparés)
  - Sélection univers: liquidité, taille, filtres fondamentaux / listage (pays/secteur)
  - Randomisation de l’ordre (anti-biais pipeline)
- Feature Engineering
  - Facteur zoo: momentum, quality, value, growth, volatility, size, liquidity, microstructure
  - Normalisation cross-sectionnelle (z-score winsorisé)
  - Neutralisation secteur/style (demean par groupe, beta-neutral)
  - Décorrélation (PCA/ICA) ou contraintes de corrélation
- Validation / IC Analytics
  - IC/RankIC par facteur, fenêtre roulante, decay exponentiel (λ ~ 0.94–0.98)
  - Stability/Turnover, hit-rate, t-stat, breadth
  - Sélection dynamique de facteurs (top-k IC par régime)
- Régimes de Marché
  - Détection (HMM, vol regimes, trend filters, Macro states)
  - Weighting par régime (ex: momentum ↑ en trend, reversion ↑ en range)
- Modèles Prédictifs
  - Lineaire régularisé, Gradient Boosting, Random Forest, XGBoost, LightGBM
  - Séquentiels (LSTM/Transformer) pour signaux horizons courts
  - Ensembling: stacking/blending + calibration isotonic
- Construction de Portefeuille
  - Mean-Variance / Risk Parity / ERC / CVaR
  - Contraintes: long-only, bounds par actif, secteurs, turnover, exposure (beta/FX/commodities)
  - Transaction cost modelling (slippage, impact non-linéaire)
- Contrôle des Risques
  - Budget de vol, VaR/CVaR, drawdown, stress tests, concentration (HHI)
  - Kill-switch / guardrails (positions max, notional, leverage, hard limits)
- Exécution
  - VWAP/TWAP, participation, slicing, smart order routing
  - Monitoring en temps réel et attribution post-trade

## Pondération Professionnelle des Facteurs

- IC-weighted: poids ∝ IC_t (ou RankIC) avec decay:  \(w_i ∝ \sum_{k=0}^{H} IC_{t-k} \cdot \lambda^k\)
- Bayesian shrinkage: combinaison de signaux avec incertitude (variance postérieure)
- Constraints:
  - Max weight par catégorie (ex: ML features ≤ 40%)
  - Diversité (min. nombre de facteurs actifs)

## Bonnes Pratiques de Validation

- Walk-forward avec pur out-of-sample, no leakage
- Purification des features (target encoding interdit sans leakage control)
- Shadow features / adversarial validation
- Backtest: commission + fees + borrow + delay

## Références Utiles

- Grinold & Kahn – Active Portfolio Management
- Zura Kakushadze – 101 Formulaic Alphas
- Marcos López de Prado – Advances in Financial ML
- MSCI Barra – Factor Models

