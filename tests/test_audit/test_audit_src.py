import json
import subprocess
from pathlib import Path


def test_audit_script_runs_and_reports_json():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'audit_src.py'
    assert script.exists(), f"Missing script: {script}"
    proc = subprocess.run(["python", str(script)], capture_output=True, text=True)
    assert proc.returncode in (0, 1), f"Unexpected return code: {proc.returncode}\n{proc.stderr}"
    data = json.loads(proc.stdout)
    assert isinstance(data, dict)
    assert 'root' in data and 'items' in data and 'status' in data
    assert isinstance(data['items'], list)


def test_audit_detects_portfoliooptimizer_and_constraints_present():
    # This test should pass fully given current repo content
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'audit_src.py'
    proc = subprocess.run(["python", str(script)], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    # find PortfolioOptimizer and Constraints
    items = { (i['module'], i['class_name']): i for i in data['items'] }
    assert ('portfolio/optimizer.py', 'PortfolioOptimizer') in items
    assert ('portfolio/constraints.py', 'Constraints') in items
    assert items[('portfolio/optimizer.py', 'PortfolioOptimizer')]['exists'] is True
    assert items[('portfolio/constraints.py', 'Constraints')]['exists'] is True
