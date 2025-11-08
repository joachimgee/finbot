"""
FinBERT Sentiment Analysis Engine.

This module provides production-grade sentiment analysis using ProsusAI/finbert,
a BERT model fine-tuned on financial news and social media.

Features:
- Lazy model loading (on first inference)
- GPU auto-detection
- Batch inference for efficiency
- Sentiment scoring ∈ [-1, +1]
- Confidence scores ∈ [0, 1]
- Robust error handling

Model: ProsusAI/finbert
- Trained on 4,840 financial news sentences
- Labels: positive, negative, neutral
- F1-score: 0.94 on financial text

Audit:
    AUDIT_FINANCE_PARTIE_5_ML.md pp.13-16 (NLP patterns)
    
Example:
    >>> engine = FinBERTEngine()
    >>> sentiment = engine.get_sentiment("Apple earnings beat expectations")
    >>> print(sentiment)
    {'score': 0.85, 'label': 'positive', 'confidence': 0.95}
    
    >>> texts = ["Bullish on tech", "Market crash imminent"]
    >>> sentiments = engine.batch_sentiment(texts)
"""

from typing import Dict, List, Optional
import logging

import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FinBERTEngine:
    """
    FinBERT sentiment analysis engine.
    
    Provides sentiment scoring using ProsusAI/finbert model with:
    - Lazy loading (model loaded on first use)
    - GPU auto-detection (CUDA if available)
    - Batch processing for efficiency
    - Normalized scores ∈ [-1, +1]
    
    Attributes:
        model_name: HuggingFace model identifier
        device: Computation device ('cuda' or 'cpu')
        batch_size: Batch size for batch inference
        model: Loaded FinBERT model (None until first use)
        tokenizer: Loaded tokenizer (None until first use)
        pipeline: HuggingFace pipeline (None until first use)
    
    Audit:
        AUDIT_FINANCE_PARTIE_5_ML.md p.13 (sentiment analysis patterns)
    """
    
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: str = "auto",
        batch_size: int = 32
    ):
        """
        Initialize FinBERT engine.
        
        Args:
            model_name: HuggingFace model identifier
            device: Device for inference ('auto', 'cuda', 'cpu')
                'auto' = CUDA if available, else CPU
            batch_size: Batch size for batch_sentiment()
        
        Raises:
            ValueError: If device is invalid
        
        Example:
            >>> engine = FinBERTEngine(device='cuda', batch_size=64)
        """
        if device not in ['auto', 'cuda', 'cpu']:
            raise ValueError(f"Invalid device: {device}. Must be 'auto', 'cuda', or 'cpu'")
        
        self.model_name = model_name
        self.batch_size = batch_size
        
        # Auto-detect device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        
        # Lazy loading - initialized on first use
        self.model: Optional[AutoModelForSequenceClassification] = None
        self.tokenizer: Optional[AutoTokenizer] = None
        self.pipeline: Optional[pipeline] = None
        
        logger.info(
            f"FinBERTEngine initialized: model={model_name}, device={device}, "
            f"batch_size={batch_size}"
        )
    
    def _load_model(self) -> None:
        """
        Lazy load FinBERT model and tokenizer.
        
        Downloads model to .cache/finbert/ on first call.
        Subsequent calls are no-ops (model already loaded).
        
        Raises:
            Exception: If model loading fails
        
        Audit:
            AUDIT_FINANCE_PARTIE_5_ML.md p.14 (lazy loading pattern)
        """
        if self.model is not None:
            return  # Already loaded
        
        logger.info(f"Loading FinBERT model ({self.model_name})...")
        
        try:
            # Load model
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                cache_dir=".cache/finbert"
            ).to(self.device)
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=".cache/finbert"
            )
            
            # Create pipeline
            self.pipeline = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                return_all_scores=False
            )
            
            logger.info("FinBERT model loaded successfully")
        
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            raise
    
    def get_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Input text (headline, article, tweet, etc.)
        
        Returns:
            Dictionary with:
            - score: Sentiment score ∈ [-1, +1]
                +1 = extremely positive
                0 = neutral
                -1 = extremely negative
            - label: Sentiment label ('positive', 'neutral', 'negative')
            - confidence: Confidence score ∈ [0, 1]
        
        Notes:
            - Empty text returns neutral (0.0)
            - Text is truncated to 512 tokens
            - Score = label_sign * confidence
        
        Example:
            >>> engine.get_sentiment("Stock surges 20% on earnings beat")
            {'score': 0.92, 'label': 'positive', 'confidence': 0.92}
        """
        self._load_model()
        
        # Handle empty text
        if not text or len(text.strip()) == 0:
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
        
        try:
            # Run inference
            result = self.pipeline(text, truncation=True, max_length=512)[0]
            
            # Map label to score
            label = result['label'].lower()
            score_map = {
                'positive': 1.0,
                'neutral': 0.0,
                'negative': -1.0
            }
            
            # Normalized score: label_sign * confidence
            base_score = score_map.get(label, 0.0)
            confidence = result['score']
            score = base_score * confidence
            
            return {
                'score': float(score),
                'label': label,
                'confidence': float(confidence)
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed for text: {e}")
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
    
    def batch_sentiment(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Analyze sentiment for multiple texts (batch mode).
        
        More efficient than calling get_sentiment() repeatedly.
        Uses GPU batch processing if available.
        
        Args:
            texts: List of texts to analyze
        
        Returns:
            List of sentiment dicts (same format as get_sentiment())
        
        Notes:
            - Processes in batches of self.batch_size
            - Empty texts return neutral
            - Errors in batch return neutral for failed items
        
        Example:
            >>> texts = [
            ...     "Bullish on tech stocks",
            ...     "Market correction expected",
            ...     "Neutral outlook for Q4"
            ... ]
            >>> sentiments = engine.batch_sentiment(texts)
            >>> print([s['score'] for s in sentiments])
            [0.87, -0.75, 0.02]
        """
        self._load_model()
        
        if not texts:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            
            try:
                # Run batch inference
                batch_results = self.pipeline(
                    batch,
                    truncation=True,
                    max_length=512,
                    batch_size=len(batch)
                )
                
                # Convert to normalized scores
                for result in batch_results:
                    label = result['label'].lower()
                    score_map = {
                        'positive': 1.0,
                        'neutral': 0.0,
                        'negative': -1.0
                    }
                    
                    base_score = score_map.get(label, 0.0)
                    confidence = result['score']
                    score = base_score * confidence
                    
                    results.append({
                        'score': float(score),
                        'label': label,
                        'confidence': float(confidence)
                    })
            
            except Exception as e:
                logger.error(
                    f"Batch {i//self.batch_size} processing failed (size={len(batch)}): {e}"
                )
                # Return neutral for failed batch
                results.extend([
                    {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
                    for _ in batch
                ])
        
        return results


__all__ = ['FinBERTEngine']
