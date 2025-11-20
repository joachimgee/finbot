import json
import runpy
from pathlib import Path


def test_recommended_repos_schema():
    # Run the script as a module to get the function
    mod_globals = runpy.run_path(str(Path('scripts/research_repos.py')))
    assert 'recommended_repos' in mod_globals
    repos = mod_globals['recommended_repos']()

    assert isinstance(repos, list)
    assert len(repos) >= 8  # au moins 8 références

    required_keys = {"name", "category", "license", "summary", "proposed_integration"}
    names = set()
    for item in repos:
        assert required_keys.issubset(item.keys())
        assert isinstance(item["name"], str) and "/" in item["name"]
        assert isinstance(item["proposed_integration"], list)
        names.add(item["name"])

    # Vérifie présence de quelques repos clés
    for must in [
        "microsoft/qlib",
        "hudson-and-thames/mlfinlab",
        "quantopian/alphalens",
        "robertmartin8/PyPortfolioOpt",
        "dppalomar/riskfolio-lib",
    ]:
        assert must in names


def test_script_outputs_json(tmp_path, monkeypatch):
    # Exécute le script et capture la sortie JSON
    p = Path('scripts/research_repos.py')
    mod_globals = runpy.run_path(str(p))
    repos = mod_globals['recommended_repos']()
    # Vérifie que c'est JSON-sérialisable
    s = json.dumps(repos)
    assert s.startswith('[') and s.endswith(']')
