#!/usr/bin/env python3
"""
methods/youtube/method2.py

Secondary strategy (placeholder). Accepts URL as argv[1] or START_URL env.
Here we just validate input and print what we'd do.

Exit codes:
  0 success (noop demo)
  2 usage / missing URL
"""

import sys
import os

def log(s: str):
    print(s, flush=True)

def main():
    url = None
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        url = sys.argv[1].strip()
    elif os.environ.get("START_URL"):
        url = os.environ["START_URL"].strip()

    if not url:
        log("[method2] No URL passed; expecting start.py to provide it")
        sys.exit(2)

    # Put alternate download logic here if desired (e.g., selenium, API, etc.)
    log(f"[method2] Got URL: {url}")
    log("[method2] (noop) Alternate method would run here.")
    sys.exit(0)

if __name__ == "__main__":
    main()
