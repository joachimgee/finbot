🎯 MISSION : Restructuration complète du projet FinBot

📋 CONTEXTE :
Tu as accès aux audits techniques exhaustifs (272 KB) de 8 forks financiers majeurs :
- backtesting.py (framework vectorisé)
- FinanceDatabase (300,000+ symboles)
- FinanceToolkit (150+ ratios)
- Finance fork (150 programmes)
- PyPortfolioOpt (Mean-Variance, HRP, BL)
- Riskfolio-Lib (24 risk measures)
- ML4T (workflows ML complets)

Ces audits sont dans docs/AUDITS/. Lis INDEX_COMPLET_AUDITS.md en premier.

🚨 RÈGLE D'OR :
Ne JAMAIS réimplémenter ce qui existe dans les forks.
Utiliser les libs DIRECTEMENT.
Wrapper SEULEMENT si nécessaire pour harmoniser l'API.

📖 INSTRUCTIONS :
1. Lis .github/copilot-instructions.md (nouvelles conventions v2.0)
2. Lis docs/AUDITS/INDEX_COMPLET_AUDITS.md (vue d'ensemble)
3. Lis docs/AUDITS/SUMMARY_AUDIT_FINBOTX.md (résumé)

✅ ACTIONS INITIALES :

1. Créer docs/ARCHITECTURE.md
   - Architecture complète (voir .github/copilot-instructions.md)
   - Diagrammes UML (classes principales)
   - Flow charts (data → features → backtest → optimize)
   - Spécifications APIs

2. Créer docs/INTEGRATION_PLAN.md
   - Plan détaillé d'intégration des forks
   - Ordre de développement (Phases 1-7)
   - Dépendances entre modules
   - Timeline estimée

3. Créer docs/API_REFERENCE.md
   - Référence complète de toutes les APIs
   - Inspiré des audits (signatures, params, returns)
   - Exemples d'usage pour chaque fonction

4. Créer requirements.txt (NOUVELLE VERSION)
   - financedatabase>=2.2.0
   - financetoolkit>=1.8.0
   - backtesting>=0.3.3
   - pypfopt>=1.5.5
   - riskfolio-lib>=6.0.0
   - (liste complète basée sur les forks)

5. Créer setup.py
   - Package configuration
   - Dependencies from requirements.txt
   - Entry points pour CLI

NE CODE RIEN POUR L'INSTANT.
Produis SEULEMENT la documentation et les plans.

RESPECTE .github/copilot-instructions.md v2.0 strictement.
