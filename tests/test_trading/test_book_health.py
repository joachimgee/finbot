"""Tests du contrôle de santé quotidien du book."""
from __future__ import annotations

from financial_analyzer.trading.book_health import (
    HealthThresholds,
    check_book_health,
)


def _pos(sym, qty, mv, pl=0.0):
    return {"symbol": sym, "qty": qty, "market_value": mv, "unrealized_pl": pl}


def _neutral_book(n=10, size=5000.0):
    """n longs + n shorts de taille égale → net 0, brut 2n×size."""
    out = []
    for i in range(n):
        out.append(_pos(f"L{i}", 10, size))
        out.append(_pos(f"S{i}", -10, -size))
    return out


def test_healthy_book_has_no_alerts() -> None:
    pos = _neutral_book(n=10, size=5000.0)  # brut 100k, net 0
    h = check_book_health(pos, equity=100_000.0, peak_equity=100_000.0)
    assert h.status == "ok" and not h.alerts
    assert h.n_longs == 10 and h.n_shorts == 10
    assert abs(h.net_exposure) < 1e-9
    assert abs(h.gross_exposure - 1.0) < 1e-9


def test_net_exposure_drift_alerts() -> None:
    pos = _neutral_book(n=10, size=5000.0)
    pos.append(_pos("EXTRA", 100, 30_000.0))  # casse la neutralité
    h = check_book_health(pos, equity=100_000.0)
    assert h.status == "warning"
    assert any("neutralité" in a for a in h.alerts)


def test_drawdown_is_critical() -> None:
    pos = _neutral_book(n=5, size=5000.0)
    h = check_book_health(pos, equity=80_000.0, peak_equity=100_000.0)
    assert h.drawdown_pct == -20.0
    assert h.status == "critical"
    assert any(a.startswith("CRITIQUE") for a in h.alerts)


def test_concentration_alert() -> None:
    pos = [_pos("BIG", 100, 20_000.0), _pos("S", -10, -20_000.0)]
    h = check_book_health(pos, equity=100_000.0,
                          thresholds=HealthThresholds(max_position_pct=0.08,
                                                      min_gross_exposure=0.1,
                                                      max_gross_exposure=2.0))
    assert any("Concentration" in a for a in h.alerts)
    assert ("BIG", 0.2) in [(s, round(w, 3)) for s, w in h.concentrated]


def test_unexpected_and_missing_vs_target() -> None:
    pos = [_pos("A", 10, 5000.0), _pos("B", -10, -5000.0), _pos("ORPHAN", 5, 100.0)]
    target = {"A": 0.5, "B": -0.5, "C": 0.5}
    h = check_book_health(pos, equity=100_000.0, target=target,
                          thresholds=HealthThresholds(min_gross_exposure=0.0,
                                                      max_gross_exposure=5.0))
    assert h.unexpected == ["ORPHAN"]
    assert h.missing == ["C"]
    assert any("hors book" in a for a in h.alerts)
    assert any("non détenue" in a for a in h.alerts)


def test_empty_book_is_coherent() -> None:
    h = check_book_health([], equity=100_000.0)
    assert h.n_positions == 0 and h.gross_exposure == 0.0
    assert h.status == "ok"  # book vide : pas d'alerte de levier (aucune position)


def test_worst_positions_sorted() -> None:
    pos = [_pos("A", 10, 5000.0, pl=-500.0), _pos("B", 10, 5000.0, pl=+200.0),
           _pos("C", -10, -5000.0, pl=-1500.0)]
    h = check_book_health(pos, equity=100_000.0,
                          thresholds=HealthThresholds(min_gross_exposure=0.0))
    assert h.worst[0][0] == "C" and h.worst[0][1] == -1500.0


def test_halt_cycle(tmp_path) -> None:
    from financial_analyzer.trading.book_health import clear_halt, raise_halt, read_halt

    p = tmp_path / "halt.json"
    assert read_halt(p).active is False          # absent -> pas de halte
    st = raise_halt("drawdown -18%", {"dd": -18.0}, path=p)
    assert st.active and "drawdown" in st.reason
    back = read_halt(p)
    assert back.active and back.metrics["dd"] == -18.0 and back.raised_at
    assert clear_halt(p) is True                 # levée manuelle
    assert read_halt(p).active is False
    assert clear_halt(p) is False                # déjà levée


def test_halt_read_is_fail_open_on_corruption(tmp_path) -> None:
    """Un état corrompu ne doit pas geler le book silencieusement (fail-open assumé)."""
    from financial_analyzer.trading.book_health import read_halt

    p = tmp_path / "halt.json"
    p.write_text("{ ceci n'est pas du json", encoding="utf-8")
    assert read_halt(p).active is False
