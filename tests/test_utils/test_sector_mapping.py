from pathlib import Path
import json
import pandas as pd

from financial_analyzer.utils.sector_mapping import load_sector_mapping, save_sector_mapping


def test_load_sector_mapping_inline_json():
    mapping = load_sector_mapping('{"AAPL":"Technology","MSFT":"Technology"}')
    assert mapping == {"AAPL": "Technology", "MSFT": "Technology"}


def test_load_sector_mapping_json_file(tmp_path: Path):
    data = {"GOOGL": "Communication Services", "AMZN": "Consumer Discretionary"}
    p = tmp_path / "map.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    mapping = load_sector_mapping(str(p))
    assert mapping == data


def test_load_sector_mapping_csv_file(tmp_path: Path):
    df = pd.DataFrame({
        "ticker": ["NVDA", "JPM"],
        "sector": ["Technology", "Financials"],
    })
    p = tmp_path / "map.csv"
    df.to_csv(p, index=False)
    mapping = load_sector_mapping(str(p))
    assert mapping == {"NVDA": "Technology", "JPM": "Financials"}


def test_save_sector_mapping_roundtrip(tmp_path: Path):
    data = {"META": "Communication Services"}
    p = tmp_path / "out.json"
    save_sector_mapping(data, str(p))
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out == data
