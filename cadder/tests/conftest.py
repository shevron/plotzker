"""cadder's tests run against the demo project in ``fixture/`` (package ``demo``)."""

import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixture"
sys.path.insert(0, str(FIXTURE / "src"))
