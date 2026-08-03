import os
import sys
from pathlib import Path

# Add src to sys.path for imports
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Désactive le cache disque pour toute la session de tests, AVANT le premier
# import de financial_analyzer.config (qui lit cette variable à l'import).
# Sans cela, des résultats mockés sont picklés dans data/cache/ et resservis
# aux tests suivants (mêmes clés de cache), rendant la suite non déterministe.
# Un test qui veut exercer le cache le réactive explicitement via
# monkeypatch.setattr(config, 'CACHE_ENABLED', True) — lu dynamiquement.
os.environ.setdefault('CACHE_ENABLED', 'false')
