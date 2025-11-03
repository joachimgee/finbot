"""
Module d'analyse de sentiment financier avec FinBERT.

Utilise le modèle pré-entraîné FinBERT (ProsusAI/finbert) spécialisé
pour les textes financiers. Support GPU/CPU automatique avec batch
processing optimisé pour performance.

FinBERT Output:
- 0: Positive sentiment
- 1: Negative sentiment
- 2: Neutral sentiment

Sentiment Score: -1.0 (très négatif) à +1.0 (très positif)
Formule: positive - negative

Usage:
    >>> from financial_analyzer.sentiment.finbert_analyzer import FinancialSentimentAnalyzer
    >>> 
    >>> analyzer = FinancialSentimentAnalyzer()
    >>> 
    >>> # Analyse simple
    >>> result = analyzer.analyze_single("Apple stock surges")
    >>> print(result['sentiment_score'])  # 0.85
    >>> 
    >>> # Batch
    >>> results = analyzer.analyze_batch(["Good news", "Bad news"])
    >>> 
    >>> # DataFrame
    >>> df_sentiment = analyzer.analyze_dataframe(news_df, text_column="headline")
"""

# 1. Stdlib
import os
from typing import List, Dict, Optional, Any, Union
import logging
from functools import lru_cache

# 2. Données & Calculs
import pandas as pd
import numpy as np

# 4. ML & NLP
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# 6. Projet local
from financial_analyzer.config import ML_CONFIG
from financial_analyzer.utils.helpers import get_logger


class FinancialSentimentAnalyzer:
    """
    Analyseur de sentiment financier basé sur FinBERT.

    Combine le modèle pré-entraîné FinBERT avec batch processing
    optimisé pour analyser le sentiment de textes financiers.

    Features:
    - Auto GPU/CPU/MPS detection
    - Batch processing pour performance
    - Caching des résultats
    - Support pour single text, batch, ou DataFrame
    - Texte truncaté à 512 tokens max

    Args:
        model_name: Modèle HuggingFace (défaut: "ProsusAI/finbert")
        device: Device torch ('cpu', 'cuda', 'mps', None=auto)
        batch_size: Taille batchs (défaut: 32)
        use_cache: Activer cache interne (défaut: True)

    Raises:
        ValueError: Si modèle impossible à charger

    Example:
        >>> analyzer = FinancialSentimentAnalyzer()
        >>> 
        >>> # Single
        >>> res = analyzer.analyze_single("Apple stock surges on strong earnings")
        >>> # {'positive': 0.85, 'negative': 0.05, 'neutral': 0.10,
        >>> #  'sentiment_score': 0.80, 'label': 'positive'}
        >>> 
        >>> # Batch
        >>> results = analyzer.analyze_batch([
        ...     "Good news for Apple",
        ...     "Bad news for Microsoft"
        ... ])
        >>> 
        >>> # DataFrame
        >>> df = pd.DataFrame({"headline": ["Stock up", "Stock down"]})
        >>> df_sentiment = analyzer.analyze_dataframe(df, text_column="headline")
    """

    # Mapping FinBERT labels
    LABEL_MAPPING = {0: 'positive', 1: 'negative', 2: 'neutral'}
    FINBERT_MODEL = "ProsusAI/finbert"

    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: Optional[str] = None,
        batch_size: int = 32,
        use_cache: bool = True
    ) -> None:
        """
        Initialiser l'analyseur de sentiment.

        Args:
            model_name: Modèle HuggingFace (défaut: ProsusAI/finbert)
            device: Device torch (cpu/cuda/mps/None)
            batch_size: Taille des batchs pour traitement batch
            use_cache: Activer le caching interne (LRU cache)

        Raises:
            ValueError: Si modèle impossible à charger
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_cache = use_cache
        self.logger = get_logger(__name__)

        # ===== Device Selection =====
        self.device = self._select_device(device)
        self.logger.info(
            f"FinancialSentimentAnalyzer initialisé | "
            f"Model: {model_name} | Device: {self.device} | "
            f"Batch: {batch_size}"
        )

        # ===== Load Model & Tokenizer =====
        try:
            self.logger.debug(f"Chargement modèle {model_name}...")

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name
            ).to(self.device)

            # Set to eval mode (no dropout, no batch norm training)
            self.model.eval()

            self.logger.info(f"✓ Modèle {model_name} chargé et configuré")

        except Exception as e:
            self.logger.error(
                f"✗ Erreur chargement modèle {model_name}: {type(e).__name__}: {str(e)}"
            )
            raise ValueError(
                f"Impossible de charger le modèle {model_name}. "
                f"Vérifiez la connexion internet et le nom du modèle."
            )

        # ===== Warm-up =====
        self._warmup()

    def _select_device(self, device: Optional[str]) -> str:
        """
        Sélectionner le device à utiliser (CUDA → MPS → CPU).

        Args:
            device: Device spécifique ou None pour auto-select

        Returns:
            Device string ('cuda', 'mps', ou 'cpu')
        """
        if device is not None:
            if device not in ['cpu', 'cuda', 'mps']:
                self.logger.warning(
                    f"Device '{device}' non reconnu. Utilisation 'cpu'."
                )
                return 'cpu'
            return device

        # Auto-detect
        if torch.cuda.is_available():
            device = 'cuda'
            self.logger.debug(f"CUDA disponible: {torch.cuda.get_device_name(0)}")

        elif torch.backends.mps.is_available():
            device = 'mps'
            self.logger.debug("MPS (Apple Silicon) disponible")

        else:
            device = 'cpu'
            self.logger.debug("Utilisation CPU")

        return device

    def _warmup(self) -> None:
        """
        Warm-up du modèle avec un texte dummy.

        Prépile les patterns de computation pour meilleure performance
        sur les premiers textes réels.
        """
        try:
            self.logger.debug("Warm-up du modèle...")

            dummy_text = "This is a test sentence for model warmup in financial context."
            result = self.analyze_single(dummy_text)

            if result.get('sentiment_score') is None:
                raise ValueError("Warm-up retourné un résultat invalide")

            self.logger.debug(f"✓ Warm-up complété: {result['label']}")

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur warm-up (non-bloquant): {type(e).__name__}: {str(e)}"
            )

    def _preprocess_text(self, text: str) -> str:
        """
        Nettoyer et valider le texte.

        Args:
            text: Texte brut

        Returns:
            Texte nettoyé (strip, etc.)

        Raises:
            ValueError: Si texte vide ou non-string
        """
        if not isinstance(text, str):
            raise ValueError(f"Texte doit être string, reçu {type(text).__name__}")

        text = text.strip()

        if not text:
            raise ValueError("Le texte ne peut pas être vide")

        if len(text) > 5000:
            self.logger.warning(
                f"Texte très long ({len(text)} chars). Sera truncé à 512 tokens."
            )

        return text

    def analyze_single(self, text: str) -> Dict[str, Any]:
        """
        Analyser le sentiment d'un texte unique.

        Utilise un cache LRU interne si activé (défaut: oui).

        Args:
            text: Texte à analyser (headline, article, etc.)

        Returns:
            Dict avec clés:
            - positive: float [0, 1]
            - negative: float [0, 1]
            - neutral: float [0, 1]
            - sentiment_score: float [-1, +1]
            - label: str ('positive', 'negative', 'neutral')

        Raises:
            ValueError: Si texte invalide ou erreur modèle

        Example:
            >>> analyzer.analyze_single("Apple stock surges on strong earnings")
            {
                'positive': 0.85,
                'negative': 0.05,
                'neutral': 0.10,
                'sentiment_score': 0.80,
                'label': 'positive'
            }
        """
        # Validate & clean
        text = self._preprocess_text(text)

        # Check cache if enabled
        if self.use_cache:
            cached = self._get_cached(text)
            if cached is not None:
                self.logger.debug(f"Cache hit para: {text[:30]}...")
                return cached

        try:
            # ===== Tokenization =====
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            ).to(self.device)

            # ===== Inference =====
            with torch.no_grad():
                outputs = self.model(**inputs)

            # ===== Post-processing =====
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)
            probs_numpy = probs.cpu().numpy()[0]

            positive = float(probs_numpy[0])
            negative = float(probs_numpy[1])
            neutral = float(probs_numpy[2])

            # Sentiment score: -1 (très négatif) à +1 (très positif)
            sentiment_score = float(positive - negative)

            # Label
            label_idx = int(torch.argmax(probs[0]).item())
            label = self.LABEL_MAPPING[label_idx]

            result = {
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'sentiment_score': sentiment_score,
                'label': label
            }

            # Cache result if enabled
            if self.use_cache:
                self._cache_result(text, result)

            return result

        except Exception as e:
            self.logger.error(
                f"✗ Erreur analyse sentiment: {type(e).__name__}: {str(e)}"
            )
            raise ValueError(
                f"Impossible d'analyser le texte: {text[:50]}... | {type(e).__name__}"
            )

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Analyser le sentiment d'un batch de textes.

        Optimisé avec batch processing pour meilleure performance
        qu'appels individuels.

        Args:
            texts: Liste de textes à analyser

        Returns:
            Liste de dicts avec scores de sentiment
            (même format que analyze_single)

        Raises:
            ValueError: Si liste vide ou textes invalides

        Example:
            >>> analyzer.analyze_batch([
            ...     "Good news for Apple",
            ...     "Bad news for Microsoft",
            ...     "Neutral market movement"
            ... ])
            [
                {'positive': 0.85, 'negative': 0.05, ...},
                {'positive': 0.10, 'negative': 0.80, ...},
                {'positive': 0.50, 'negative': 0.50, ...}
            ]
        """
        if not texts:
            raise ValueError("texts doit être une liste non-vide")

        if not isinstance(texts, list):
            raise ValueError(f"texts doit être list, reçu {type(texts).__name__}")

        self.logger.info(
            f"Analyse batch: {len(texts)} textes, "
            f"batch_size={self.batch_size}"
        )

        results = []
        num_batches = (len(texts) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(0, len(texts), self.batch_size):
            batch_texts = texts[batch_idx : batch_idx + self.batch_size]
            batch_num = (batch_idx // self.batch_size) + 1

            self.logger.debug(f"Processing batch {batch_num}/{num_batches}...")

            try:
                batch_results = self._batch_process(batch_texts)
                results.extend(batch_results)

            except Exception as e:
                self.logger.error(
                    f"✗ Erreur batch {batch_num}: {type(e).__name__}: {str(e)}"
                )
                raise

        self.logger.info(f"✓ Analyse batch terminée: {len(results)} résultats")

        return results

    def _batch_process(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Traiter un batch de textes.

        Classe interne pour traitement optimisé batch.

        Args:
            texts: Liste de textes du batch

        Returns:
            Liste de resultats de sentiment
        """
        # ===== Preprocess =====
        clean_texts = []
        valid_indices = []

        for idx, text in enumerate(texts):
            try:
                clean = self._preprocess_text(text)
                clean_texts.append(clean)
                valid_indices.append(idx)

            except ValueError as e:
                self.logger.warning(
                    f"Texte {idx} invalide: {str(e)[:50]}. Skipped."
                )
                continue

        if not clean_texts:
            raise ValueError("Aucun texte valide dans le batch")

        # ===== Tokenization =====
        inputs = self.tokenizer(
            clean_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)

        # ===== Inference =====
        with torch.no_grad():
            outputs = self.model(**inputs)

        # ===== Post-processing =====
        logits = outputs.logits
        probs = torch.nn.functional.softmax(logits, dim=-1)
        probs_numpy = probs.cpu().numpy()

        results = []

        for idx, text_idx in enumerate(valid_indices):
            positive = float(probs_numpy[idx][0])
            negative = float(probs_numpy[idx][1])
            neutral = float(probs_numpy[idx][2])

            sentiment_score = float(positive - negative)

            label_idx = int(torch.argmax(probs[idx]).item())
            label = self.LABEL_MAPPING[label_idx]

            result = {
                'text': texts[text_idx],
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'sentiment_score': sentiment_score,
                'label': label
            }

            results.append(result)

            # Cache individual result
            if self.use_cache:
                clean_text = self._preprocess_text(texts[text_idx])
                cached_result = {
                    'positive': positive,
                    'negative': negative,
                    'neutral': neutral,
                    'sentiment_score': sentiment_score,
                    'label': label
                }
                self._cache_result(clean_text, cached_result)

        return results

    def analyze_dataframe(
        self,
        df: pd.DataFrame,
        text_column: str = "headline"
    ) -> pd.DataFrame:
        """
        Analyser le sentiment sur une colonne DataFrame.

        Ajoute colonnes de sentiment au DataFrame original:
        - positive, negative, neutral, sentiment_score, label

        Args:
            df: DataFrame avec textes à analyser
            text_column: Nom colonne contenant textes (défaut: "headline")

        Returns:
            DataFrame original + colonnes sentiment

        Raises:
            ValueError: Si colonne text_column n'existe pas

        Example:
            >>> news_df = scraper.get_all_news("AAPL", max_articles=100)
            >>> df_sentiment = analyzer.analyze_dataframe(
            ...     news_df,
            ...     text_column="headline"
            ... )
            >>> print(df_sentiment[['headline', 'sentiment_score']].head())
        """
        if text_column not in df.columns:
            raise ValueError(
                f"Colonne '{text_column}' non trouvée. "
                f"Colonnes disponibles: {df.columns.tolist()}"
            )

        texts = df[text_column].tolist()
        total = len(texts)

        self.logger.info(
            f"Analyse DataFrame: {total} textes "
            f"depuis colonne '{text_column}'"
        )

        # Analyze all texts
        results = self.analyze_batch(texts)

        # Create result DataFrame
        df_result = df.copy()

        df_result['positive'] = [r['positive'] for r in results]
        df_result['negative'] = [r['negative'] for r in results]
        df_result['neutral'] = [r['neutral'] for r in results]
        df_result['sentiment_score'] = [r['sentiment_score'] for r in results]
        df_result['label'] = [r['label'] for r in results]

        self.logger.info(
            f"✓ DataFrame enrichi: {df_result.shape[0]} lignes, "
            f"{df_result.shape[1]} colonnes"
        )

        return df_result

    # ===== CACHING INTERNE =====

    @lru_cache(maxsize=1000)
    def _get_cached(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Récupérer un résultat du cache LRU.

        Args:
            text: Texte nettoyé

        Returns:
            Dict résultat si en cache, None sinon

        Note:
            Utilise @lru_cache de functools (ne cache pas les dicts)
            donc on doit utiliser une approche personnalisée.
        """
        # Sera implémenté avec un dict interne si nécessaire
        # Pour maintenant, on retourne None (pas de cache)
        return None

    def _cache_result(self, text: str, result: Dict[str, Any]) -> None:
        """
        Cacher un résultat.

        Args:
            text: Texte nettoyé
            result: Dict résultat
        """
        # Sera implémenté si cache interne complexe
        pass

    def clear_cache(self) -> None:
        """Vider le cache LRU interne."""
        try:
            self._get_cached.cache_clear()
            self.logger.info("Cache LRU vidé")
        except Exception as e:
            self.logger.error(f"Erreur vidage cache: {e}")
