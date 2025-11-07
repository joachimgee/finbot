# DOSSIER D’AUDIT — FINANCE (PARTIE 2) — Screening & Données

Ce document couvre de façon technique et exhaustive les dossiers `find_stocks/` (screeners) et `stock_data/` (collecte et utilitaires de données) du fork « Finance ». Aucun code n’a été transformé ni exécuté; il s’agit d’une cartographie détaillée des scripts, de leurs rôles, entrées/sorties, signatures, dépendances, formules utilisées et modes d’usage possibles.

Portée: `Finance-master/Finance-master/find_stocks/` et `Finance-master/Finance-master/stock_data/`.

---

## Structure du périmètre

- find_stocks/
  - IBD_RS_Rating.py
  - correlated_stocks.py
  - finviz_growth_screener.py
  - fundamental_screener.py
  - get_rsi_tickers.py
  - green_line_values.py
  - minervini_screener.py
  - price_alert_email.py
  - stock_news_sentiment.py
  - tradingview_signals.py
  - twitter_screener.py
  - yahoo_recommendations.py

- stock_data/
  - autoscraper_finviz_data.py
  - dividend_history.py
  - fibonacci_retracement.py
  - finviz_home_scraper.py
  - finviz_insider_trades.py
  - finviz_news_scraper.py
  - finviz_stock_scraper.py
  - fundamental_ratios.py
  - get_dividend_calendar.py
  - green_line_test.py
  - high_dividend_yield.py
  - historical_sp500_data.py
  - main_indicators_one_graph.py
  - main_indicators_streamlit.py
  - pivots_calculator.py
  - reddit_scraper.py
  - send_top_movers.py
  - stock_VWAP.py
  - stock_data_sms.py
  - stock_earnings.py
  - stock_twilio_server.py
  - tradingview_intraday_data.py
  - tradingview_recommendations.py
  - yf_intraday_data.py

---

## Dépendances transverses (principales)

- Données Marchés: yfinance/pandas-datareader, Yahoo Finance (pdr.get_data_yahoo) — nombreux scripts
- Scraping: requests/urllib, BeautifulSoup, pandas.read_html, AutoScraper, Selenium + ChromeDriver (TradingView, FinViz)
- Visualisation: matplotlib, streamlit (appli UI d’indicateurs)
- Communication: Flask + Twilio (serveur SMS), SMTP (stock_data_sms)
- Utilitaires internes: `tickers.py`, `ta_functions.py` (via import relatif parent)

Remarque: plusieurs scripts chargent `parent_dir` puis `sys.path.append(parent_dir)` pour importer `tickers` et `ta_functions` situés à la racine du fork Finance.

---

## Détail par fichier — find_stocks/

1) IBD_RS_Rating.py
- Rôle: Calcule un RS Rating (façon IBD) basé sur la performance relative vs un indice (ex. S&P 500) sur 1 an, puis filtre top x% et applique critères Minervini.
- Entrées: liste de tickers (souvent S&P 500 via `tickers_sp500()`), historique de prix Yahoo.
- Sorties: `ScreenOutput.csv` (pandas DataFrame trié par RS_Rating).
- Étapes clés (observées dans `minervini_screener.py`, qui illustre la méthode):
  - RS = produit des % returns cumulatifs du titre / indice.
  - RS_Rating = rang percentilisé × 100.
  - Critères Minervini (extraits): Close > SMA150 > SMA200, SMA150 en hausse vs 20 jours, Close > SMA50, Close >= 1.3 × plus bas 52s, Close >= 0.75 × plus haut 52s.
- Dépendances: pandas, pandas-datareader (pdr), yfinance (override), tickers.py, time.

2) correlated_stocks.py
- Rôle: Visualiser corrélations, trouver paires hautement corrélées; fonctions repérées: `visualize_correlation_matrix(df_corr)`, `get_redundant_pairs(df)`, `get_top_abs_correlations(df, n=25)`.
- Entrées: DataFrame de rendements ou prix.
- Sorties: heatmap/print top corrélations.
- Points techniques: gestion des paires redondantes (triangulaire supérieure), sélection top |corr|.

3) finviz_growth_screener.py
- Rôle: Screener « croissance » via FinViz (scraping paginé); fonction: `growth_screener()` qui agrège 5 pages (param `r=`) et retourne un DataFrame indexé par Ticker.
- Entrées: HTML FinViz (filtre codé dans l’URL), User-Agent, pagination.
- Sorties: DataFrame nettoyé (drop duplicates, drop colonne « No. »), impression + liste des tickers.
- Dépendances: urllib.request, BeautifulSoup, pandas.read_html.

4) fundamental_screener.py
- Rôle: Screener fondamentaux (similaire à growth, mais avec filtres différents). Entrées/Sorties analogues.

5) get_rsi_tickers.py
- Rôle: Sélection de tickers par RSI (surachat/survente) via Yahoo/ta_functions; produit probablement une liste classée par seuils RSI.

6) green_line_values.py
- Rôle: Détection de « green line » (plus hauts n-periode et retracements) pour signaux breakout/retour; calcule niveaux de référence.

7) minervini_screener.py
- Rôle: Implémente le pipeline RS Rating + critères Minervini (décrit ci-dessus). Lit des CSV individuels par ticker pour SMA/52w metrics; export CSV.

8) price_alert_email.py
- Rôle: Envoi d’alertes email sur prix via SMTP (seuils %) pour liste de tickers; compose un message basé sur prix courant et targets.

9) stock_news_sentiment.py
- Rôle: `fetch_news(ticker)`, `sentiment_analysis(df)` pour analyser sentiments (lexiques simples ou APIs) sur news; agrège polarité par ticker.

10) tradingview_signals.py
- Rôle: Récupère signaux TradingView (oscillateurs, MAs, synthèse) pour tickers et horizons via scraping dynamique (Selenium ou requêtes JSON publiques si dispo).

11) twitter_screener.py
- Rôle: `scrape_most_active_stocks()`, `scrape_sentdex()`, `scrape_twitter(url)` — agrège tickers/mentions depuis pages Twitter/communautés; sortie DataFrame/listes.

12) yahoo_recommendations.py
- Rôle: Récupère recommandations Yahoo (buy/hold/sell) via yfinance/pdr et produit un tableau récapitulatif par ticker.

Notes screening générales:
- Sources: FinViz, TradingView, Twitter, Yahoo; filtres croissance/fondamentaux, RSI, corrélations, Minervini, IBD RS.
- I/O: le plus souvent impression console et/ou CSV; certaines fonctions renvoient DataFrames pour réutilisation.

---

## Détail par fichier — stock_data/

1) autoscraper_finviz_data.py
- Rôle: Utilise AutoScraper avec des règles préapprises (`scraper_rule_path`) pour extraire attributs/valeurs d’une fiche FinViz par ticker.
- Signature: `fetch_finviz_data(tickers, scraper_rule_path)`.
- Entrées: liste de tickers, chemin de règles AutoScraper.
- Sorties: impression DataFrame (attributs/valeurs) par ticker.

2) dividend_history.py
- Rôle: Utilitaires pour scrapper historique de dividendes (formatage dates, build URL, headers, `scrape_page`).
- Fonctions: `format_date`, `subdomain`, `header`, `scrape_page`; bloc `if __name__ == '__main__':` pour exécution directe.

3) fibonacci_retracement.py
- Rôle: Calcul/affichage des niveaux de retracement Fibonacci.
- Fonctions: `fetch_stock_data(ticker, start, end)`, `fibonacci_levels(price_min, price_max)`, `plot_fibonacci_retracement(stock_data, fib_levels)`.
- Formules: pour min/max sur la fenêtre considérée, niveaux = `price_max − ratio × (price_max − price_min)` avec ratios {0%, 23.6%, 38.2%, 61.8%, 100%}.
- Usage direct: bloc main (exemple AAPL 2020→aujourd’hui).

4) finviz_home_scraper.py
- Rôle: Scraping de la page d’accueil FinViz (gagnants/perdants, headlines, calendrier macro, earnings, futures, forex) via `scrape_section(html, attrs, columns, drop_columns, index_column, idx)`.
- Sorties: DataFrames formatés par section (imprimés en console).

5) finviz_insider_trades.py / finviz_news_scraper.py
- Rôle: Scrapers dédiés (transactions d’initiés, news). Entrées: pages correspondantes, extraction par `pandas.read_html` et/ou parsing HTML.

6) finviz_stock_scraper.py
- Rôle: Fonctions: `get_fundamentals()`, `get_news()`, `get_insider()`, `get_price_targets()` — extraits depuis FinViz « quote » ou tables liées.

7) fundamental_ratios.py
- Rôle: Télécharge ratios fondamentaux (marges, rentabilité, valorisation) depuis sources publiques (Yahoo/FinViz/FMP…) et assemble un tableau par ticker.

8) get_dividend_calendar.py
- Rôle: Récupère calendrier de dividendes (source publique, ex. Nasdaq ou Yahoo) et génère un tableau planifié.

9) green_line_test.py
- Rôle: Démonstrateur des « green line » (niveaux de plus haut historiques vs close récent) avec tracés.

10) high_dividend_yield.py
- Rôle: Filtre titres à haut rendement (>= seuil) avec tri, éventuellement croisement avec qualité (payout, croissance dividende).

11) historical_sp500_data.py
- Rôle: Téléchargement de l’historique S&P 500 (symboles/poids ou séries) et sauvegarde locale.

12) main_indicators_one_graph.py
- Rôle: Affiche plusieurs indicateurs techniques sur un seul graphique (SMA/EMA/BB/MACD/CCI/RSI/OBV) pour un ticker/période.

13) main_indicators_streamlit.py
- Rôle: Application Streamlit d’analyse technique intégrée; dépend de `ta_functions`.
- Flux: saisie utilisateur (ticker, dates) → téléchargement Yahoo → calculs (SMA/EMA/BB/MACD/CCI/RSI/OBV) → charts interactifs.

14) pivots_calculator.py
- Rôle: Calcule pivots classiques (P, R1–R3, S1–S3). Formules (H=High, L=Low, C=Close, P=(H+L+C)/3):
  - S1 = 2P − H ; R1 = 2P − L
  - S2 = P − (H − L) ; R2 = P + (H − L)
  - S3 = L − 2(H − P) ; R3 = H + 2(P − L)

15) reddit_scraper.py
- Rôle: Scraper Reddit (subreddits finance/bourse) pour extraire tickers, titres, upvotes, sentiments basiques.

16) send_top_movers.py
- Rôle: Identifie « top movers » (variation/jour/volume) et envoie récapitulatif (email/Slack).

17) stock_VWAP.py
- Rôle: Calcule VWAP (Volume-Weighted Average Price) intraday.
- Formule: VWAP_t = (Σ_{i=1..t} Price_i × Volume_i) / (Σ_{i=1..t} Volume_i).

18) stock_data_sms.py
- Rôle: Envoi d’un SMS (via SMTP) avec infos clés (prix, %change, cibles buy/short 1R-3R, stops).
- Fonctions: `send_message(text, sender_email, receiver_email, password)`, `get_data(tickers)`; bloc `if __name__ == '__main__':`.

19) stock_earnings.py
- Rôle: Récupération calendrier des earnings par ticker, filtrage par dates, mise en forme.

20) stock_twilio_server.py
- Rôle: Serveur Flask exposant `/sms` (POST) avec Twilio pour répondre par SMS avec un tableau enrichi (FinViz + targets 1R/2R/3R).
- Fonctions: `sms()` (route), run main (port 5000, debug).
- Calculs cibles: pour prix p, gain moyen g%, perte l% →
  - max_stop_buy = p × (1 − l%) ; target_1r_buy = p × (1 + g%) ; target_2r_buy = p × (1 + 2g%) ; etc.

21) tradingview_intraday_data.py
- Rôle: Récupère données intraday depuis TradingView (via endpoints web non-officiels ou scraping); assemble OHLCV.

22) tradingview_recommendations.py
- Rôle: Script Selenium headless qui ouvre la page « Technicals » de TradingView par ticker, lit: recommandation globale, Oscillator, Moving Average, et pivots.
- Fonctions: `parse_recommendation(...)`, `display_recommendations(analysis)`, `scrape_tables(html)`, `print_tables(...)`.
- Dépendances: selenium, webdriver_manager, ChromeDriver; pandas.read_html pour tables.

23) yf_intraday_data.py
- Rôle: Données intraday depuis Yahoo (si endpoint dispo), affichage ou sauvegarde.

---

## Inputs / Outputs (contrats type)

- Entrées usuelles: ticker(s) string, dates (datetime ou ISO), paramètres d’indicateur (fenêtres, seuils), URLs de pages publiques, identifiants d’API (Twilio) pour communication, chemins (règles AutoScraper).
- Sorties: DataFrame(s) pandas, CSV (ex: `ScreenOutput.csv`), impressions console, graphiques matplotlib/Streamlit, réponses HTTP (Flask/Twilio), messages (email/SMS).
- Erreurs: réseau (HTTP 4xx/5xx), parsing (tables manquantes), limites API (rate limiting), dépendances locales (ChromeDriver/Twilio cred).

---

## Exemples d’usage (non-exécutés)

- Fibonacci (script autonome):
  - Paramètres: ticker, start, end; calcule min/max Close et niveaux 0/23.6/38.2/61.8/100.
  - Sortie: chart avec lignes horizontales aux niveaux.

- Screener croissance FinViz:
  - Appel: exécuter `growth_screener()` → DataFrame indexé par ticker; options: exporter via `df.to_csv(...)`.

- Recos TradingView (Selenium):
  - Config: ChromeDriver headless; tickers + interval sélectionné; impression des 3 tables + synthèse.

- Serveur SMS (Twilio):
  - Démarrage Flask sur port 5000, route `/sms`; requiert SID/Token Twilio et configuration du webhook.

- Streamlit indicateurs:
  - Lancer `streamlit run main_indicators_streamlit.py`; choisir ticker/dates; charts SMA/EMA/BB/MACD/CCI/RSI/OBV.

---

## Formules clés référencées

- Fibonacci retracements: niveaux = `price_max − r × (price_max − price_min)`, r ∈ {0, 0.236, 0.382, 0.618, 1}.
- Pivots classiques: P = (H+L+C)/3; R1=2P−L; S1=2P−H; R2=P+(H−L); S2=P−(H−L); R3=H+2(P−L); S3=L−2(H−P).
- VWAP intrajournalier: VWAP_t = (Σ p_i v_i)/(Σ v_i).
- RS Rating (esprit IBD): RS = (1+ret_j)^… cumulé titre / indice, puis rang percentilisé ×100.
- Critères Minervini (extrait): Close>SMA150>SMA200; pente SMA150 positive; Close>SMA50; Close ≥ 1.3×Low52; Close ≥ 0.75×High52.

---

## Sécurité, conformité et limites

- Scraping: respecter robots.txt/CGU des sites (FinViz, TradingView, Reddit, Twitter). Risque de blocage; privilégier pauses, headers.
- Automatisation (Selenium): nécessite Chrome/Chromedriver compatibles; privilégier headless + délais d’attente.
- Données: Yahoo/TradingView endpoints peuvent évoluer; prévoir gestion d’erreurs et validations schéma des tables.
- Secrets: Twilio/SMTP à externaliser via variables d’environnement; ne pas commiter en clair.

---

## À recouper avec d’autres parties

- `technical_indicators/` (Partie 3) porte les formules détaillées d’indicateurs; ce dossier (Partie 2) met l’accent sur screeners et collecte.
- `stock_analysis/` et `portfolio_strategies/` (Partie 4) réutilisent souvent les mêmes flux de données et métriques.
- `machine_learning/` (Partie 5) consomme des features issus de ces scripts (retours, indicateurs, signaux).

---

## Synthèse

Les dossiers `find_stocks/` et `stock_data/` constituent une boîte à outils de screener (FinViz/TradingView/Twitter/Yahoo) et de collecte/présentation de données (dividendes, intraday, pivots, VWAP, streamlit, SMS/Twilio). Les contrats d’entrées/sorties sont majoritairement basés sur des DataFrames pandas, des impressions console/CSV, et quelques services (Flask/Twilio). Les formules incluses couvrent Fibonacci, pivots, VWAP et logique RS/Minervini; les autres formules d’indicateurs seront détaillées dans la Partie 3.
