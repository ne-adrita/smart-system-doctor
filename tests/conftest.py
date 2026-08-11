import os
import sys
from pathlib import Path

# Force the test configuration before any app module is imported.
os.environ["SSD_TESTING"] = "1"
os.environ["SSD_LOG_CONSOLE"] = "0"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
