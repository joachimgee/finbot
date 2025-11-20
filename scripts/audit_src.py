#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import ast

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "financial_analyzer"


@dataclass
class Target:
    module: str
    class_name: str


TARGETS: List[Target] = [
    Target("ml/feature_engineering.py", "AlphaFactorEngine"),
    Target("ml_features/feature_engineer.py", "FeatureEngineer"),
    Target("features/technical.py", "TechnicalFeatureEngine"),
    Target("features/fundamental.py", "FundamentalFeatureEngine"),
    Target("ml/sentiment_factor_engine.py", "SentimentFactorEngine"),
    Target("analysis/ml_predictor.py", "MLPredictor"),
    Target("portfolio/optimizer.py", "PortfolioOptimizer"),
    Target("portfolio/constraints.py", "Constraints"),
]


@dataclass
class AuditItem:
    module: str
    class_name: str
    file: Optional[str]
    exists: bool


@dataclass
class AuditReport:
    root: str
    items: List[AuditItem]

    def to_dict(self):
        return {
            "root": self.root,
            "items": [asdict(i) for i in self.items],
            "status": "OK" if all(i.exists for i in self.items) else "PARTIAL",
        }


def find_class_in_file(fp: Path, class_name: str) -> bool:
    try:
        src = fp.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    try:
        tree = ast.parse(src)
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return True
    return False


def run_audit() -> AuditReport:
    items: List[AuditItem] = []
    for t in TARGETS:
        file_path = SRC_ROOT / t.module
        exists = False
        file_str: Optional[str] = None
        if file_path.exists():
            file_str = str(file_path)
            exists = find_class_in_file(file_path, t.class_name)
        items.append(AuditItem(module=t.module, class_name=t.class_name, file=file_str, exists=exists))
    return AuditReport(root=str(SRC_ROOT), items=items)


def main(argv: List[str]) -> int:
    report = run_audit()
    out = json.dumps(report.to_dict(), indent=2)
    print(out)
    # Exit code 0 if all present, 1 otherwise
    return 0 if all(i.exists for i in report.items) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
