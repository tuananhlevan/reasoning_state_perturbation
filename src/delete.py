#!/usr/bin/env python3
"""Delete one worker's temporary download and extraction directory."""
import argparse, shutil
from pathlib import Path

def delete_workdir(work_dir, temp_root):
    target, root = Path(work_dir).resolve(), Path(temp_root).resolve()
    if target == root or root not in target.parents: raise ValueError(f"Unsafe cleanup target: {work_dir}")
    if target.exists(): shutil.rmtree(target)

def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("work_dir", type=Path); parser.add_argument("--temp-root", type=Path, default=Path(".work")); args = parser.parse_args(); delete_workdir(args.work_dir, args.temp_root); print(f"Removed {args.work_dir}"); return 0
if __name__ == "__main__": raise SystemExit(main())
