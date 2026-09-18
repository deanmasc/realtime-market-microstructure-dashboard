import sys
from pathlib import Path

# The app imports modules relative to src/ (e.g. `from processing.metrics import ...`)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
