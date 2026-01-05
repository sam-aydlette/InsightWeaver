"""
InsightWeaver package main module
Allows running as: python -m src
"""

import sys
from pathlib import Path

# Add parent to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import main

if __name__ == "__main__":
    main()
