#!/usr/bin/env python3
"""
startdetails.py

Loads and runs detail-analysis helpers (findtemp.py, findkey.py) from the project's details folder.

Fix applied:
- Updated expected details directory from 'link2stems/details' to 'link2aws/details'.
- Keeps 'youtube2audwstems/details' as a valid fallback.

This script does NOT auto-create folders; it will exit with a clear error if not found.
"""

import os
import sys
import importlib.util
from datetime import datetime
from typing import Optional

# -------------------------
# Logging helper
# -------------------------
def log(msg: str) -> None:
    now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{now} {msg}")

# -------------------------
# Dynamic module loader
# -------------------------
def import_from_path(filepath: str, module_name: str):
    """Import a module from an exact file path."""
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {module_name} from {filepath}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def import_from_details(details_dir: str, filename: str):
    """Import a module that lives inside DETAILS_DIR by filename."""
    filepath = os.path.join(details_dir, filename)
    if not os.path.exists(filepath):
        log(f"ERROR: Could not find {filename} in {details_dir}")
        return None
    module_name = os.path.splitext(filename)[0]
    mod = import_from_path(filepath, module_name)
    log(f"[use] {filename} = {filepath}")
    return mod

# -------------------------
# Resolve ROOT and DETAILS_DIR
# -------------------------
def resolve_details_dir() -> Optional[str]:
    """
    Finds the correct details directory.
    Priority:
      1) link2aws/details
      2) youtube2audwstems/details  (fallback)
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    candidates = [
        os.path.join(root_dir, "link2aws", "details"),
        os.path.join(root_dir, "youtube2audwstems", "details"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    return None

# -------------------------
# Main
# -------------------------
def main() -> None:
    details_dir = resolve_details_dir()

    if not details_dir:
        # Updated message to reflect corrected expectation
        log("ERROR: details folder missing (expected link2aws/details or youtube2audwstems/details).")
        sys.exit(1)

    log(f"[path] Selected DETAILS_DIR: {details_dir}")

    # Import detail modules (only if present)
    findtemp = import_from_details(details_dir, "findtemp.py")
    findkey = import_from_details(details_dir, "findkey.py")

    log("------------------------------------------------------------------------")

    # Optional: run their main() if available
    if findtemp or findkey:
        log("Modules import attempted. Running available test entry points...")

    if findtemp and hasattr(findtemp, "main"):
        log("Running findtemp.main()...")
        try:
            findtemp.main()
        except Exception as e:
            log(f"ERROR while running findtemp.main(): {e}")

    if findkey and hasattr(findkey, "main"):
        log("Running findkey.main()...")
        try:
            findkey.main()
        except Exception as e:
            log(f"ERROR while running findkey.main(): {e}")

    if not findtemp and not findkey:
        log("No detail modules were loaded. Nothing to run.")

# -------------------------
# Entrypoint
# -------------------------
if __name__ == "__main__":
    main()
