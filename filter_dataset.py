#!/usr/bin/env python3
"""Convenience wrapper for src/filter_dataset.py."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(src_dir))

from filter_dataset import main

if __name__ == "__main__":
    main()
