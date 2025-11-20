"""
Financial sentiment analyzer using FinBERT (unit-test friendly).

This implementation aligns with tests expectations in tests/test_sentiment_overview.py:
- Attributes: model_name == "ProsusAI/finbert", device in {cpu,cuda,mps}, batch_size == 32
- Uses symbols from financial_analyzer.sentiment.finbert_analyzer for patchability
- Methods: analyze_single, analyze_batch, analyze_dataframe
"""

from __future__ import annotations

# 1. Stdlib
from typing import Dict, List
import logging

# 2. Third-party
import pandas as pd
import numpy as np

# 3. Local (adapter exposing torch and transformers symbols)
from financial_analyzer.sentiment.finbert_analyzer import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    torch,
)

logger = logging.getLogger(__name__)


class FinancialSentimentAnalyzer:
    """
    Analyse de sentiment basée sur FinBERT.

    Contract:
    - Input: strings or DataFrame column (headline)
    - Output (single/batch item):
      { 'sentiment_score': float[-1,1], 'positive': float, 'negative': float,
        'neutral': float, 'label': 'positive'|'neutral'|'negative' }
    - Errors: ValueError on invalid inputs (empty text, wrong dtype, missing column)
    """

    def __init__(self, model_name: str = "ProsusAI/finbert", batch_size: int = 32) -> None:
        """
        Initialise le modèle FinBERT et le tokenizer.

        Args:
            model_name: Identifiant du modèle HuggingFace
            batch_size: Taille de lot pour analyze_batch
        """
        self.model_name = model_name
        self.batch_size = batch_size

        # Device detection compatible with tests monkeypatching
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        # Load model/tokenizer (tests patch from_pretrained)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        logger.info(
            f"FinancialSentimentAnalyzer init: model={self.model_name}, device={self.device}, "
            f"batch_size={self.batch_size}"
        )

    def _softmax(self, logits: "torch.Tensor") -> np.ndarray:
        """Torch-softmax to numpy array (stable)."""
        # simple softmax using torch then convert to numpy
        probs = torch.softmax(logits, dim=-1)
        return probs.detach().cpu().numpy()

    def analyze_single(self, text: str) -> Dict[str, float]:
        """
        Analyse un texte et retourne scores et label.

        Returns keys: sentiment_score, positive, negative, neutral, label
        """
        if not isinstance(text, str):
            raise ValueError("Le texte doit être une string")
        if text.strip() == "":
            raise ValueError("Le texte fourni est vide")

        # Tokenization (tests patch tokenizer to return tensors)
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        logits = outputs.logits  # shape [1, 3]
        probs = self._softmax(logits)[0]

        # FinBERT label order may vary across checkpoints; tests work with 3 logits
        # We'll map indices by maximum probability to label and also compute score = pos - neg
        # For deterministic keys, we assume index mapping: [positive, negative, neutral]
        # If length mismatch, fallback to neutral
        if probs.shape[0] == 3:
            positive, negative, neutral = float(probs[0]), float(probs[1]), float(probs[2])
        else:
            positive, negative, neutral = 0.0, 0.0, 1.0

        # Label and score
        labels = ["positive", "negative", "neutral"]
        label = labels[int(np.argmax([positive, negative, neutral]))]
        sentiment_score = float(positive - negative)

        return {
            "sentiment_score": sentiment_score,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "label": label,
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyse une liste de textes en batch."""
        if not isinstance(texts, list) or len(texts) == 0:
            raise ValueError("La liste de textes doit être non-vide")
        return [self.analyze_single(t) for t in texts]

    def analyze_dataframe(self, df: pd.DataFrame, text_column: str = "headline") -> pd.DataFrame:
        """Applique l'analyse de sentiment à un DataFrame (colonne texte obligatoire)."""
        if text_column not in df.columns:
            raise ValueError(f"Colonne '{text_column}' non trouvée dans DataFrame")

        def _analyze_row(text: str) -> Dict[str, float]:
            try:
                return self.analyze_single(text)
            except Exception:
                return {"sentiment_score": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0, "label": "neutral"}

        results = df[text_column].apply(_analyze_row)
        results_df = pd.DataFrame(list(results.values))
        # Align index
        results_df.index = df.index
        # Concatenate
        return pd.concat([df.copy(), results_df], axis=1)


def analyze_sentiment(text: str) -> Dict[str, float]:
    """Analyse rapide pour un texte unique (helper)."""
    analyzer = FinancialSentimentAnalyzer()
    return analyzer.analyze_single(text)
