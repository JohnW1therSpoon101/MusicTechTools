#!/usr/bin/env python3
"""
getlink.py — Prompt for a YouTube/YouTube Shorts URL.
Spec:
- Display "==INSERT==LINK=="
- If invalid: print "invalid, try again" and re-prompt
- If valid: print "This works!" then echo the URL
- Only accept YouTube / YouTube Shorts for now
"""

import sys
import re
from urllib.parse import urlparse, parse_qs

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

def _has_video_id_query(url: str) -> bool:
    """Check for /watch?v=... style URLs."""
    try:
        u = urlparse(url)
        if u.netloc.lower() not in YOUTUBE_HOSTS:
            return False
        if u.path.lower() == "/watch":
            qs = parse_qs(u.query or "")
            v = qs.get("v", [""])[0].strip()
            return bool(v)
        return False
    except Exception:
        return False

def _is_youtu_be(url: str) -> bool:
    """Check youtu.be/<id> short links."""
    try:
        u = urlparse(url)
        if u.netloc.lower() not in YOUTUBE_HOSTS:
            return False
        if u.netloc.lower().endswith("youtu.be"):
            # Path like /<video_id>
            return bool(u.path.strip("/"))
        return False
    except Exception:
        return False

def _is_shorts(url: str) -> bool:
    """Check youtube.com/shorts/<id> links."""
    try:
        u = urlparse(url)
        if u.netloc.lower() not in YOUTUBE_HOSTS:
            return False
        # Accept /shorts/<id> (optionally with trailing slash or query)
        return bool(re.fullmatch(r"/shorts/[^/]+/?", u.path))
    except Exception:
        return False

def is_valid_youtube_url(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    # Require scheme
    if not url.lower().startswith(("http://", "https://")):
        return False
    return _has_video_id_query(url) or _is_youtu_be(url) or _is_shorts(url)

def main() -> int:
    while True:
        try:
            user = input("==INSERT==LINK==\n").strip()
        except (EOFError, KeyboardInterrupt):
            print("invalid, try again")
            return 1

        if is_valid_youtube_url(user):
            print("This works!")
            # Echo the URL on its own line so start.py can parse it reliably
            print(user)
            return 0
        else:
            print("invalid, try again")

if __name__ == "__main__":
    sys.exit(main())
