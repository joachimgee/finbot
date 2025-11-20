"""Sentiment Pipeline (FinBERT Stub Integration)

Fournit un score de sentiment agrégé quotidien pour ajuster le stress test.
Si le modèle FinBERT n'est pas disponible, retourne 0 (neutre).

Usage:
    from financial_analyzer.ml.sentiment_pipeline import SentimentAnalyzer
    analyzer = SentimentAnalyzer()
    score = analyzer.compute_sentiment_score([
        "Stocks fall as recession fears grow",
        "Tech giants beat earnings expectations"
    ])

Le score est dans [-1,1]. Un score négatif renforce VaR / Monte Carlo stress.
"""
from __future__ import annotations
import numpy as np
from typing import List

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    _FINBERT_AVAILABLE = True
except Exception:  # pragma: no cover
    _FINBERT_AVAILABLE = False


class SentimentAnalyzer:
    """Analyseur de sentiment financier basé sur FinBERT (ou stub)."""
    def __init__(self):
        if _FINBERT_AVAILABLE:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone")
                self.model = AutoModelForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")
                self.model.eval()
            except Exception:
                # Fallback si téléchargement impossible
                self.tokenizer = None
                self.model = None
        else:
            self.tokenizer = None
            self.model = None

    def compute_sentiment_score(self, headlines: List[str]) -> float:
        """Calcule un score de sentiment moyen.
        Args:
            headlines: Liste de titres d'actualité.
        Returns:
            Score moyen dans [-1,1]. 0 = neutre.
        """
        if not headlines:
            return 0.0
        if self.tokenizer is None or self.model is None:
            # Heuristique légère: mots négatifs vs positifs
            negatives = {"crash","loss","fear","recession","bankruptcy","default"}
            positives = {"beat","growth","record","surge","upgrade","profit"}
            scores = []
            for h in headlines:
                h_low = h.lower()
                score = 0
                score -= sum(w in h_low for w in negatives)
                score += sum(w in h_low for w in positives)
                scores.append(score)
            raw = np.mean(scores)
            return float(np.clip(raw/5.0, -1, 1))
        # FinBERT inference
        scores = []
        for h in headlines:
            inputs = self.tokenizer(h, return_tensors="pt", truncation=True)
            with torch.no_grad():
                out = self.model(**inputs)
            probs = torch.softmax(out.logits, dim=-1).numpy()[0]
            # FinBERT order: [neutral, positive, negative]
            neutral, positive, negative = probs
            score = positive - negative  # range [-1,1]
            scores.append(score)
        return float(np.mean(scores))


def sentiment_adjustment_factor(sentiment_score: float) -> float:
    """Convertit sentiment en facteur d'ajustement risque.
    sentiment <= -0.5 => augmenter VaR ~ +15%
    sentiment >= +0.5 => réduire VaR ~ -10%
    """
    if sentiment_score <= -0.5:
        return 1.15
    if sentiment_score >= 0.5:
        return 0.90
    # interpolation linéaire centrale
    return 1.0 + (-0.10 * sentiment_score)  # sentiment négatif => facteur >1

__all__ = ["SentimentAnalyzer","sentiment_adjustment_factor"]
