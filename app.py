"""Root-level entry point for Streamlit Dashboard."""

import sys
import importlib
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure all src modules reload cleanly when files are updated
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("src.") or mod_name == "src":
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass

import src.dashboard.app
try:
    importlib.reload(src.dashboard.app)
except Exception:
    pass

if __name__ == "__main__":
    src.dashboard.app.main()
