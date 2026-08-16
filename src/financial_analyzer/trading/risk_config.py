"""Configurations de risque committées (source unique de vérité des limites).

Le daemon calait jusqu'ici les limites du ``RiskGuard`` sur des **nombres magiques
inline** (position 35 %, drawdown −25 %, levier 1.5…), lâches pour un début live et
**sans** les garde-fous portefeuille (vol/VaR/paris-effectifs restaient inactifs).
Ce module centralise et **documente** deux profils :

* :func:`live_risk_config` — profil **conservateur** pour le passage live : limites
  serrées, **aucun levier**, et garde-fous portefeuille (corrélation-aware) **actifs**.
  C'est le profil que le critère #5 du runbook attend réellement.
* :func:`daemon_paper_risk_config` — profil **paper** actuel du daemon (plus lâche :
  on observe le comportement naturel de la stratégie sans le brider). Reproduit à
  l'identique les valeurs inline historiques → aucun changement de comportement paper.

Les limites en dollars sont **paramétrées par le capital** (pas de montant magique) :
un même profil vaut à 10 k$ comme à 1 M$. Le capital et la tolérance de perte
restent une **décision opérateur** (critère #10 du runbook) — ce module fournit la
*structure* des limites, l'opérateur fournit le capital.
"""
from __future__ import annotations

__all__ = [
    "REQUIRED_LIMIT_KEYS",
    "daemon_paper_risk_config",
    "live_risk_config",
    "risk_config_for",
]

#: Clés qu'une config *live* doit toutes renseigner (non-``None``) pour être jugée
#: complète — utilisé par le rapport de préparation au live (critère #5).
REQUIRED_LIMIT_KEYS = (
    "max_position_size", "max_position_pct", "max_total_positions",
    "max_drawdown", "max_daily_loss", "max_leverage", "enable_circuit_breaker",
    "max_portfolio_vol", "max_var_95", "min_effective_bets",
)


def live_risk_config(capital: float) -> dict:
    """Profil de risque **conservateur** pour le live, paramétré par le capital.

    Chaque limite est justifiée (début prudent, sûreté d'abord) :

    * ``max_position_pct=0.10`` / ``max_position_size=10 % du capital`` — au plus
      10 % du book sur un nom (bien plus serré que les 35 % du paper) ;
    * ``max_total_positions=20`` — book concentré et lisible ;
    * ``max_drawdown=-0.10`` — halte à −10 %, aligné sur le critère P&L du runbook (#2) ;
    * ``max_daily_loss=2 % du capital`` — coupe-circuit de perte journalière ;
    * ``max_leverage=1.0`` — **aucun levier** au démarrage live ;
    * ``enable_circuit_breaker=True`` ;
    * garde-fous **portefeuille** (corrélation-aware) actifs : vol ex-ante ≤ 20 %,
      VaR 95 % 1 j ≤ 3 %, ≥ 5 paris effectifs (``1/Σwᵢ²``) — attrapent la
      concentration qu'un cap *par nom* ne voit pas.

    Args:
        capital: capital alloué (USD). Doit être > 0.
    """
    cap = max(0.0, float(capital))
    return {
        "max_position_size": cap * 0.10,
        "max_position_pct": 0.10,
        "max_total_positions": 20,
        "max_drawdown": -0.10,
        "max_daily_loss": cap * 0.02,
        "max_leverage": 1.0,
        "enable_circuit_breaker": True,
        "max_portfolio_vol": 0.20,
        "max_var_95": 0.03,
        "min_effective_bets": 5.0,
    }


def daemon_paper_risk_config(capital: float) -> dict:
    """Profil **paper** actuel du daemon (observation-friendly, plus lâche).

    Reproduit **exactement** les valeurs inline historiques du daemon (position
    35 %, jusqu'à 100 lignes, drawdown −25 %, perte journalière 10 %, levier 1.5) :
    câbler ce module ne change donc rien au comportement paper. Les garde-fous
    portefeuille restent inactifs en paper (on observe la stratégie brute).

    Args:
        capital: equity courante (USD) pour caler les planchers en dollars.
    """
    cap = float(capital)
    return {
        "max_position_size": max(cap, 50000.0),
        "max_position_pct": 0.35,
        "max_total_positions": 100,
        "max_drawdown": -0.25,
        "max_daily_loss": max(cap * 0.10, 1000.0),
        "max_leverage": 1.5,
        "enable_circuit_breaker": True,
    }


def risk_config_for(mode: str, capital: float) -> dict:
    """Renvoie le profil de risque adapté au mode (``'live'`` → conservateur)."""
    return live_risk_config(capital) if mode == "live" else daemon_paper_risk_config(capital)
