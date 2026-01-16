#!/usr/bin/env python3
"""
InsightWeaver - Main Application Entry Point
Multi-command CLI for intelligent RSS feed analysis and trust verification
"""

import sys
from pathlib import Path

# Add src to path if running directly
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.cli.app import cli

if __name__ == "__main__":
    cli()
