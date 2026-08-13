"""Signal Fusion Engine - Integrated Multi-Source Signal Generation

Fusionne les signaux de TOUS les modules disponibles:
- Features techniques (TechnicalFeatureEngine)
- Features fondamentales (FundamentalFeatureEngine)
- Sentiment en temps réel (RealtimeSentimentPipeline)
- Prédictions LSTM (LSTMPredictor)
- ML factor scoring (SentimentFactorEngine, NewsSignalGenerator)
- RL signals (RLTradingPipeline)

Architecture:
    1. Collecte données multi-sources en parallèle
    2. Score chaque source indépendamment
    3. Fusion pondérée bayésienne
    4. Sortie signal composite + confiance

Author: FinBot Professional Edition
Date: 2025-11-24
Version: 1.0.0
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class SignalComponent:
    """Composante individuelle d'un signal multi-source."""
    
    source: str  # 'technical', 'fundamental', 'sentiment', 'ml_lstm', 'ml_factor', 'rl'
    score: float  # [-1, 1] ou [0, 1] normalisé
    confidence: float  # [0, 1]
    weight: float = 1.0  # Poids relatif dans fusion finale
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FusedSignal:
    """Signal fusionné final avec décomposition."""
    
    symbol: str
    composite_score: float  # [-1, 1] ou [0, 1]
    confidence: float  # [0, 1]
    components: List[SignalComponent]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Export vers dict pour CSV/JSON."""
        result = {
            'symbol': self.symbol,
            'composite_score': self.composite_score,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }
        # Ajouter composantes individuelles
        for comp in self.components:
            result[f'{comp.source}_score'] = comp.score
            result[f'{comp.source}_confidence'] = comp.confidence
        return result


class SignalFusionEngine:
    """Moteur de fusion multi-sources pour signaux de trading.
    
    Intègre TOUS les modules disponibles dans FinBot:
    - Technical features (20+ indicateurs)
    - Fundamental features (40+ ratios)
    - Sentiment (Twitter, Reddit, News, FinBERT)
    - LSTM predictions (deep learning)
    - ML factor models (news signals, events)
    - RL agents (trained policies)
    
    Fusion bayésienne avec gestion gracieuse des échecs.
    
    Attributes:
        source_weights: Poids relatifs de chaque source (normalisés à 1.0)
        min_sources: Nombre minimum de sources pour signal valide
        cache: Cache des signaux récents (évite recalcul)
        fallback_mode: Si True, continue même si certains modules échouent
    """
    
    DEFAULT_WEIGHTS = {
        'technical': 0.20,
        'fundamental': 0.25,
        'sentiment': 0.15,
        'ml_lstm': 0.20,
        'ml_factor': 0.10,
        'rl': 0.10,
    }

    # Sources dont le contenu n'est PAS encore un vrai signal validé/entraîné.
    # Elles s'abstiennent (retournent None) au lieu d'injecter une constante 0.5
    # qui, une fois pondérée, tirerait le score composite vers le neutre sans
    # apporter d'information — c'est du bruit déguisé en signal. Tant qu'un
    # modèle réel (fondamentaux point-in-time, LSTM entraîné, factor/RL models)
    # n'est pas câblé, ces sources restent silencieuses et la fusion renormalise
    # sur les seules sources réelles (technical, sentiment). Voir
    # docs/SYSTEM_ASSESSMENT_AND_ROADMAP.md (P0).
    ABSTAINING_SOURCES = {
        'fundamental': "aucun modèle fondamental point-in-time câblé (placeholder constant)",
        'ml_lstm': "aucun LSTM entraîné chargé (proxy momentum 5j non validé)",
        'ml_factor': "aucun modèle factor/news entraîné (placeholder constant)",
        'rl': "aucune policy RL entraînée chargée (placeholder constant)",
    }

    def __init__(
        self,
        source_weights: Optional[Dict[str, float]] = None,
        min_sources: int = 2,
        fallback_mode: bool = True,
        cache_ttl_minutes: int = 15,
        weighting_history: Optional[pd.DataFrame] = None,
        auto_reweight: bool = True,
    ):
        """
        Initialize fusion engine.
        
        Args:
            source_weights: Custom weights per source (auto-normalized)
            min_sources: Minimum sources required for valid signal
            fallback_mode: Continue if some sources fail
            cache_ttl_minutes: Cache lifetime
            weighting_history: Historique des retours par source pour réallocation evidence-based
            auto_reweight: Si True et history fourni, recalcule les poids
        """
        self.source_weights = source_weights or self.DEFAULT_WEIGHTS.copy()
        # Normaliser poids
        total = sum(self.source_weights.values())
        if total > 0:
            self.source_weights = {k: v / total for k, v in self.source_weights.items()}
        
        self.min_sources = min_sources
        self.fallback_mode = fallback_mode
        self.cache_ttl_minutes = cache_ttl_minutes
        self.cache: Dict[str, Tuple[FusedSignal, datetime]] = {}
        # Sources déjà signalées comme abstentionnistes (log une seule fois).
        self._abstained_logged: set[str] = set()
        
        # Initialize sub-engines (lazy loading). Les sources LSTM/ML-factor/RL
        # *s'abstiennent* (aucun modèle entraîné câblé — cf. _get_*_signal ->
        # _abstain) : on ne charge donc PLUS deep_learning/ml/rl ici (couche
        # recherche, hors du chemin de décision live). Le boundary est verrouillé
        # par tests/test_architecture/test_layering.py.
        self._technical_engine = None
        self._fundamental_engine = None
        self._sentiment_pipeline = None

        # Evidence-based reweighting si historique fourni
        if auto_reweight and weighting_history is not None and not weighting_history.empty:
            try:
                from financial_analyzer.integration.weighting_engine import WeightingEngine
                we = WeightingEngine()
                result = we.compute_weights(weighting_history)
                if result.weights:
                    # Mapper seulement sur sources existantes
                    for src, w in result.weights.items():
                        if src in self.source_weights:
                            self.source_weights[src] = w
                    logger.info(f"✅ Reweighting evidence-based appliqué: {self.source_weights}")
            except Exception as e:
                logger.warning(f"⚠️ Reweighting échoué, utilisation des poids par défaut: {e}")
        logger.info(f"SignalFusionEngine initialized: weights={self.source_weights}, min_sources={self.min_sources}")

    def update_weights_from_history(self, history: pd.DataFrame, min_change: float = 0.02) -> Dict[str, float]:
        """Met à jour dynamiquement les poids à partir d'un nouvel historique.

        Args:
            history: DataFrame retours par source.
            min_change: Seuil de changement relatif pour appliquer update (évite churn).

        Returns:
            Nouveau dictionnaire de poids.
        """
        if history is None or history.empty:
            return self.source_weights
        try:
            from financial_analyzer.integration.weighting_engine import WeightingEngine
            result = WeightingEngine().compute_weights(history)
            if not result.weights:
                return self.source_weights
            # Appliquer seulement si changement significatif global
            delta = sum(abs(result.weights.get(k, 0) - self.source_weights.get(k, 0)) for k in self.source_weights)
            if delta < min_change:
                logger.debug("Changement de poids < seuil, pas d'update")
                return self.source_weights
            self.source_weights.update({k: v for k, v in result.weights.items() if k in self.source_weights})
            logger.info(f"🔄 Poids mis à jour dynamiquement: {self.source_weights}")
            return self.source_weights
        except Exception as e:
            logger.warning(f"⚠️ update_weights_from_history échoué: {e}")
            return self.source_weights
    
    def _abstain(self, source: str) -> None:
        """Fait abstenir une source stub (retourne None), en journalisant une fois.

        Injecter une constante (0.5) pour une source sans vrai modèle revient à
        diluer le signal composite avec du bruit neutre. On préfère l'abstention
        explicite : la fusion renormalise alors sur les seules sources réelles.
        """
        if source not in self._abstained_logged:
            reason = self.ABSTAINING_SOURCES.get(source, "source non implémentée")
            logger.warning(
                f"⏸️  Source '{source}' s'abstient (poids retiré de la fusion) : {reason}"
            )
            self._abstained_logged.add(source)
        return None

    def _init_technical_engine(self):
        """Lazy init TechnicalFeatureEngine."""
        if self._technical_engine is None:
            try:
                from financial_analyzer.features.technical import TechnicalFeatureEngine
                # TechnicalFeatureEngine requires OHLCV - will be provided per-call
                self._technical_engine = True  # Mark as available
                logger.info("✅ TechnicalFeatureEngine available")
            except Exception as e:
                logger.warning(f"⚠️  TechnicalFeatureEngine unavailable: {e}")
                self._technical_engine = False
        return self._technical_engine if self._technical_engine not in (None, False) else None
    
    def _init_fundamental_engine(self):
        """Lazy init FundamentalFeatureEngine."""
        if self._fundamental_engine is None:
            try:
                from financial_analyzer.features.fundamental import FundamentalFeatureEngine
                self._fundamental_engine = FundamentalFeatureEngine()
                logger.info("✅ FundamentalFeatureEngine loaded")
            except Exception as e:
                logger.warning(f"⚠️  FundamentalFeatureEngine unavailable: {e}")
                self._fundamental_engine = False
        return self._fundamental_engine if self._fundamental_engine is not False else None
    
    def _init_sentiment_pipeline(self):
        """Lazy init RealtimeSentimentPipeline."""
        if self._sentiment_pipeline is None:
            try:
                from financial_analyzer.sentiment.realtime_pipeline import RealtimeSentimentPipeline
                self._sentiment_pipeline = RealtimeSentimentPipeline(
                    api_keys={},  # Will try to load from env
                    cache_ttl=self.cache_ttl_minutes * 60
                )
                logger.info("✅ RealtimeSentimentPipeline loaded")
            except Exception as e:
                logger.warning(f"⚠️  RealtimeSentimentPipeline unavailable: {e}")
                self._sentiment_pipeline = False
        return self._sentiment_pipeline if self._sentiment_pipeline is not False else None
    
    # NB : les anciens _init_lstm_predictor / _init_ml_factor_engine /
    # _init_rl_pipeline ont été SUPPRIMÉS. Ils n'étaient jamais appelés (code mort)
    # et importaient la couche recherche (deep_learning/ml/rl) dans le chemin live
    # pour rien. Les sources correspondantes s'abstiennent via _get_*_signal ->
    # _abstain ; elles restent listées dans ABSTAINING_SOURCES (registre de la
    # discipline P0), sans charger aucun modèle.

    def _get_technical_signal(
        self,
        symbol: str,
        price_data: pd.DataFrame
    ) -> Optional[SignalComponent]:
        """
        Génère signal technique (RSI, MACD, Bollinger, etc.).
        
        Args:
            symbol: Symbole
            price_data: OHLCV dataframe
        
        Returns:
            SignalComponent ou None si échec
        """
        engine_available = self._init_technical_engine()
        if engine_available is None:
            return None
        
        try:
            from financial_analyzer.features.technical import TechnicalFeatureEngine
            engine = TechnicalFeatureEngine(ohlcv=price_data)
            features = engine.compute()
            if features.empty:
                return None
            
            # Normalisation simple basée sur indicateurs clés
            latest = features.iloc[-1]
            
            # RSI (oversold/overbought)
            rsi_signal = 0.0
            if 'rsi_14' in latest:
                rsi = float(latest['rsi_14'])
                if rsi < 30:
                    rsi_signal = 0.7  # Oversold = buy signal
                elif rsi > 70:
                    rsi_signal = 0.3  # Overbought = sell signal
                else:
                    rsi_signal = 0.5
            
            # MACD histogram
            macd_signal = 0.5
            if 'macd_histogram' in latest:
                macd_hist = float(latest['macd_histogram'])
                macd_signal = 0.5 + np.clip(macd_hist * 10, -0.5, 0.5)
            
            # Bollinger position
            bb_signal = 0.5
            if all(k in latest for k in ['bollinger_upper', 'bollinger_lower']):
                close = float(price_data['close'].iloc[-1])
                bb_upper = float(latest['bollinger_upper'])
                bb_lower = float(latest['bollinger_lower'])
                bb_range = bb_upper - bb_lower
                if bb_range > 0:
                    position = (close - bb_lower) / bb_range
                    bb_signal = float(np.clip(position, 0, 1))
            
            # Moyenne pondérée
            composite = 0.4 * rsi_signal + 0.3 * macd_signal + 0.3 * bb_signal
            confidence = 0.75  # Indicateurs techniques = fiables mais pas parfaits
            
            return SignalComponent(
                source='technical',
                score=float(composite),
                confidence=confidence,
                weight=self.source_weights.get('technical', 1.0),
                metadata={'rsi_signal': rsi_signal, 'macd_signal': macd_signal, 'bb_signal': bb_signal}
            )
        
        except Exception as e:
            logger.debug(f"Technical signal failed for {symbol}: {e}")
            return None
    
    def _get_fundamental_signal(
        self,
        symbol: str,
        fundamental_data: Optional[Dict] = None
    ) -> Optional[SignalComponent]:
        """
        Génère signal fondamental (P/E, ROE, debt ratios, etc.).
        
        Args:
            symbol: Symbole
            fundamental_data: Données fondamentales (si disponibles)
        
        Returns:
            SignalComponent ou None si échec
        """
        # Abstention : aucun modèle fondamental point-in-time n'est câblé ici.
        # L'ancienne implémentation renvoyait un score constant 0.5 (neutre), ce
        # qui injectait du bruit pondéré dans la fusion sans aucune information.
        # Tant que FundamentalFeatureEngine.compute() n'est pas branché sur des
        # ratios réels et point-in-time, cette source reste silencieuse.
        return self._abstain('fundamental')
    
    def _get_sentiment_signal(
        self,
        symbol: str,
        lookback_hours: int = 24
    ) -> Optional[SignalComponent]:
        """
        Génère signal sentiment (Twitter, Reddit, News).
        
        Args:
            symbol: Symbole
            lookback_hours: Période d'analyse
        
        Returns:
            SignalComponent ou None si échec
        """
        pipeline = self._init_sentiment_pipeline()
        if pipeline is None:
            return None
        
        try:
            sentiment_scores = pipeline.get_sentiment([symbol], lookback_hours=lookback_hours)
            if symbol not in sentiment_scores:
                return None
            
            score = sentiment_scores[symbol]
            # Normaliser de [-1, 1] à [0, 1]
            normalized_score = (score + 1) / 2
            confidence = 0.6  # Sentiment = volatile
            
            return SignalComponent(
                source='sentiment',
                score=float(normalized_score),
                confidence=confidence,
                weight=self.source_weights.get('sentiment', 1.0),
                metadata={'raw_sentiment': score}
            )
        
        except Exception as e:
            logger.debug(f"Sentiment signal failed for {symbol}: {e}")
            return None
    
    def _get_lstm_signal(
        self,
        symbol: str,
        price_data: pd.DataFrame
    ) -> Optional[SignalComponent]:
        """
        Génère signal LSTM (prédiction returns futurs).
        
        Args:
            symbol: Symbole
            price_data: Données prix historiques
        
        Returns:
            SignalComponent ou None si échec
        """
        # Abstention : le LSTMPredictor est construit mais jamais entraîné ni
        # chargé depuis des poids. L'ancien code n'utilisait même pas le modèle —
        # il renvoyait un proxy de momentum 5 jours (score = 0.5 + returns*10),
        # étiqueté « ml_lstm » et pondéré à 20 %. Ce proxy court-terme n'est pas
        # validé (nos survivants OOS sont momentum_12_1 et reversion_sma_200d).
        # On s'abstient jusqu'à ce qu'un vrai modèle entraîné soit chargé.
        return self._abstain('ml_lstm')
    
    def _get_ml_factor_signal(
        self,
        symbol: str
    ) -> Optional[SignalComponent]:
        """
        Génère signal ML factor (news events, earnings, etc.).
        
        Args:
            symbol: Symbole
        
        Returns:
            SignalComponent ou None si échec
        """
        # Abstention : aucun modèle factor/news entraîné n'est câblé. L'ancien
        # code renvoyait un score constant 0.5 — du bruit neutre pondéré à 10 %.
        return self._abstain('ml_factor')
    
    def _get_rl_signal(
        self,
        symbol: str,
        price_data: pd.DataFrame
    ) -> Optional[SignalComponent]:
        """
        Génère signal RL (agent entraîné).
        
        Args:
            symbol: Symbole
            price_data: Données prix
        
        Returns:
            SignalComponent ou None si échec
        """
        # Abstention : aucune policy RL entraînée n'est chargée. L'ancien code
        # renvoyait un score constant 0.5 — du bruit neutre pondéré à 10 %.
        return self._abstain('rl')
    
    def generate_signal(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        fundamental_data: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Optional[FusedSignal]:
        """
        Génère signal fusionné pour un symbole.
        
        Args:
            symbol: Symbole à analyser
            price_data: DataFrame OHLCV
            fundamental_data: Données fondamentales optionnelles
            use_cache: Utiliser cache si disponible
        
        Returns:
            FusedSignal ou None si échec
        """
        # Check cache
        if use_cache and symbol in self.cache:
            cached_signal, cache_time = self.cache[symbol]
            age_minutes = (datetime.now() - cache_time).total_seconds() / 60
            if age_minutes < self.cache_ttl_minutes:
                logger.debug(f"Using cached signal for {symbol} (age: {age_minutes:.1f}min)")
                return cached_signal
        
        # Collecter signaux de toutes sources
        components: List[SignalComponent] = []
        
        # 1. Technical
        tech_signal = self._get_technical_signal(symbol, price_data)
        if tech_signal:
            components.append(tech_signal)
        
        # 2. Fundamental
        fund_signal = self._get_fundamental_signal(symbol, fundamental_data)
        if fund_signal:
            components.append(fund_signal)
        
        # 3. Sentiment
        sent_signal = self._get_sentiment_signal(symbol)
        if sent_signal:
            components.append(sent_signal)
        
        # 4. LSTM
        lstm_signal = self._get_lstm_signal(symbol, price_data)
        if lstm_signal:
            components.append(lstm_signal)
        
        # 5. ML Factor
        ml_signal = self._get_ml_factor_signal(symbol)
        if ml_signal:
            components.append(ml_signal)
        
        # 6. RL
        rl_signal = self._get_rl_signal(symbol, price_data)
        if rl_signal:
            components.append(rl_signal)
        
        # Vérifier seuil minimum
        if len(components) < self.min_sources:
            if not self.fallback_mode:
                logger.warning(f"{symbol}: insufficient sources ({len(components)} < {self.min_sources})")
                return None
            else:
                logger.debug(f"{symbol}: using {len(components)} sources (min: {self.min_sources})")
        
        if not components:
            return None
        
        # Fusion bayésienne pondérée par confiance
        weighted_sum = 0.0
        weight_sum = 0.0
        confidence_sum = 0.0
        
        for comp in components:
            effective_weight = comp.weight * comp.confidence
            weighted_sum += comp.score * effective_weight
            weight_sum += effective_weight
            confidence_sum += comp.confidence
        
        if weight_sum == 0:
            return None
        
        composite_score = weighted_sum / weight_sum
        avg_confidence = confidence_sum / len(components)
        
        fused_signal = FusedSignal(
            symbol=symbol,
            composite_score=composite_score,
            confidence=avg_confidence,
            components=components
        )
        
        # Update cache
        self.cache[symbol] = (fused_signal, datetime.now())
        
        return fused_signal
    
    def generate_signals_batch(
        self,
        symbols: List[str],
        price_data_dict: Dict[str, pd.DataFrame],
        fundamental_data_dict: Optional[Dict[str, Dict]] = None,
        progress_callback: Optional[callable] = None
    ) -> pd.DataFrame:
        """
        Génère signaux pour batch de symboles.
        
        Args:
            symbols: Liste symboles
            price_data_dict: Dict {symbol: price_df}
            fundamental_data_dict: Dict {symbol: fundamental_dict}
            progress_callback: Fonction appelée avec (idx, total)
        
        Returns:
            DataFrame avec colonnes: symbol, composite_score, confidence, *_score, *_confidence
        """
        results = []
        
        for idx, symbol in enumerate(symbols):
            if progress_callback and idx % 50 == 0:
                progress_callback(idx, len(symbols))
            
            price_data = price_data_dict.get(symbol)
            if price_data is None or price_data.empty:
                continue
            
            fundamental_data = fundamental_data_dict.get(symbol) if fundamental_data_dict else None
            
            fused_signal = self.generate_signal(symbol, price_data, fundamental_data)
            if fused_signal:
                results.append(fused_signal.to_dict())
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        logger.info(f"Generated {len(df)} fused signals from {len(symbols)} symbols")
        
        return df
    
    def clear_cache(self):
        """Vide le cache de signaux."""
        self.cache.clear()
        logger.info("Signal cache cleared")
    
    def get_stats(self) -> Dict:
        """Retourne statistiques d'utilisation."""
        active_sources = []
        if self._technical_engine not in (None, False):
            active_sources.append('technical')
        if self._fundamental_engine not in (None, False):
            active_sources.append('fundamental')
        if self._sentiment_pipeline not in (None, False):
            active_sources.append('sentiment')
        # ml_lstm / ml_factor / rl : sources en abstention (aucun modèle entraîné) —
        # jamais « actives ». Elles figurent dans source_weights/ABSTAINING_SOURCES
        # comme registre de discipline, pas comme contributeurs.

        return {
            'active_sources': active_sources,
            'source_weights': self.source_weights,
            'cache_size': len(self.cache),
            'min_sources': self.min_sources,
            'fallback_mode': self.fallback_mode,
        }
