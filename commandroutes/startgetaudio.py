#!/usr/bin/env python3
"""
startgetaudio.py

- Uses getlink.py to capture a link & platform tag.
- Routes to the proper method:
    • YouTube  → methods/youtube/method1.py, then method2.py, then method3.py (fallback chain)
    • Instagram→ methods/instagram/instamethod1.py
- Tries in-process calls first; if not available/compatible, falls back to
  running the method script as a CLI subprocess with the URL.
- On success: prints the absolute path to the downloaded file and returns to menu.py.
- On failure: prints a clear error log and returns to menu.py.

Search paths for:
  getlink.py:                 */(youtube2audwstems|link2stems)/getlink.py
  methods/youtube/method*.py: */(youtube2audwstems|link2stems)/methods/youtube/method[1-3].py
  methods/instagram/instamethod1.py: */(youtube2audwstems|link2stems)/methods/instagram/instamethod1.py
"""

import os
import re
import sys
import json
import traceback
import importlib.util
import inspect
import subprocess
from datetime import datetime
from typing import Optional, Tuple, List

# ---------- Logging helpers ----------

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{now()}] {msg}")

def hr() -> None:
    print("-" * 72)

# ---------- FS discovery helpers ----------

def repo_root_from_here() -> str:
    here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(here))  # <repo_root>/commandroutes/...

def candidates_for_content_roots(repo_root: str) -> List[str]:
    parent = os.path.dirname(repo_root)
    return [
        os.path.join(repo_root, "youtube2audwstems"),
        os.path.join(repo_root, "link2stems"),
        os.path.join(parent, "youtube2audwstems"),
        os.path.join(parent, "link2stems"),
    ]

def find_file_in_known_places(repo_root: str, rel_parts: List[str]) -> Optional[str]:
    for root in candidates_for_content_roots(repo_root):
        candidate = os.path.join(root, *rel_parts)
        if os.path.isfile(candidate):
            return candidate
    return None

def find_getlink_py(repo_root: str) -> Optional[str]:
    return find_file_in_known_places(repo_root, ["getlink.py"])

def find_youtube_methods(repo_root: str) -> List[str]:
    """
    Return existing YouTube methods in priority order: method1.py, method2.py, method3.py
    """
    paths = []
    for name in ("method1.py", "method2.py", "method3.py"):
        p = find_file_in_known_places(repo_root, ["methods", "youtube", name])
        if p:
            paths.append(p)
    # Legacy fallbacks (methods/method1.py etc.)
    if not paths:
        p = find_file_in_known_places(repo_root, ["methods", "method1.py"])
        if p:
            paths.append(p)
    return paths

def find_instagram_method_py(repo_root: str) -> Optional[str]:
    return find_file_in_known_places(repo_root, ["methods", "instagram", "instamethod1.py"])

def find_menu_py(repo_root: str) -> Optional[str]:
    menu_local = os.path.join(repo_root, "menu.py")
    return menu_local if os.path.isfile(menu_local) else None

# ---------- Safe dynamic import ----------

def import_by_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {module_name} at {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

# ---------- getlink integration ----------

def call_getlink(getlink_mod) -> Tuple[str, str]:
    """
    Accepts:
      get_link_info() -> {"platform": "...", "url": "..."} | (platform, url) | JSON str
      get_link()      -> "<url>"  (platform inferred)
      main()/run()    -> any of the above forms
    """
    if hasattr(getlink_mod, "get_link_info"):
        info = getlink_mod.get_link_info()
        if isinstance(info, dict) and info.get("platform") and info.get("url"):
            return (str(info["platform"]).strip(), str(info["url"]).strip())
        if isinstance(info, (list, tuple)) and len(info) >= 2:
            return (str(info[0]).strip(), str(info[1]).strip())
        if isinstance(info, str):
            try:
                obj = json.loads(info)
                if obj.get("platform") and obj.get("url"):
                    return (str(obj["platform"]).strip(), str(obj["url"]).strip())
            except Exception:
                pass

    if hasattr(getlink_mod, "get_link"):
        url = str(getlink_mod.get_link()).strip()
        if url:
            return (infer_platform_from_url(url), url)

    for fn in ("main", "run"):
        if hasattr(getlink_mod, fn):
            res = getattr(getlink_mod, fn)()
            if isinstance(res, dict) and res.get("platform") and res.get("url"):
                return (str(res["platform"]).strip(), str(res["url"]).strip())
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                return (str(res[0]).strip(), str(res[1]).strip())
            if isinstance(res, str):
                url = res.strip()
                if url:
                    return (infer_platform_from_url(url), url)

    raise ValueError("getlink.py did not provide a usable link/platform.")

# ---------- Platform detection ----------

Y_PAT = re.compile(r"(youtube\.com|youtu\.be)", re.I)
IG_PAT = re.compile(r"(instagram\.com)", re.I)

def infer_platform_from_url(url: str) -> str:
    if Y_PAT.search(url):
        return "youtube"
    if IG_PAT.search(url):
        return "instagram"
    return "youtube"

def normalize_platform(p: str) -> str:
    s = (p or "").strip().lower()
    if "youtube" in s or "short" in s:
        return "youtube"
    if "instagram" in s:
        return "instagram"
    return "youtube"

# ---------- In-process downloader (if module exposes functions) ----------

_POSSIBLE_OUTPUT_ATTRS = (
    "LAST_OUTPUT_PATH", "OUTPUT_PATH", "last_output", "last_file", "output_path"
)

def _normalize_path(p: Optional[str]) -> Optional[str]:
    if not p or not isinstance(p, str):
        return None
    p = p.strip().strip('"').strip("'")
    return os.path.abspath(p) if os.path.exists(p) else None

def _output_from_module_vars(mod) -> Optional[str]:
    for name in _POSSIBLE_OUTPUT_ATTRS:
        if hasattr(mod, name):
            p = getattr(mod, name)
            norm = _normalize_path(p if isinstance(p, str) else None)
            if norm:
                return norm
    return None

def _invoke_downloader_callable(func, url: str, mod) -> Optional[str]:
    sig = inspect.signature(func)
    required_positional = [
        p for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.default is inspect._empty
    ]
    if len(required_positional) >= 1:
        rv = func(url)
        return _normalize_path(rv) or _output_from_module_vars(mod)
    os.environ["YT2AUDIO_URL"] = url
    rv = func()
    return _normalize_path(rv) or _output_from_module_vars(mod)

def call_downloader_module_inprocess(mod, url: str) -> Optional[str]:
    for fn in ("download_audio", "download", "run", "main"):
        if hasattr(mod, fn):
            func = getattr(mod, fn)
            try:
                out_path = _invoke_downloader_callable(func, url, mod)
                if out_path:
                    return os.path.abspath(out_path)
            except Exception:
                continue
    return None

# ---------- Subprocess fallback (for CLI-style method scripts) ----------

# capture absolute paths to common audio types even with spaces
_PATH_RE = re.compile(r'(/[^:\n\r\t]*?\.(?:wav|mp3|m4a|aac|flac|ogg|opus))', re.IGNORECASE)

def _pick_path_from_stdout(stdout: str) -> Optional[str]:
    if not stdout:
        return None
    matches = _PATH_RE.findall(stdout)
    for cand in reversed(matches):
        p = cand.strip().strip('"').strip("'")
        if os.path.isabs(p) and os.path.exists(p):
            return os.path.abspath(p)
    return None

def run_method_cli(python_exe: str, script_path: str, url: str, cwd: Optional[str]=None) -> Tuple[int, str, str, Optional[str]]:
    env = os.environ.copy()
    env["YT2AUDIO_URL"] = url  # in case the script supports env fallback
    try:
        proc = subprocess.run(
            [python_exe, script_path, url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            check=False
        )
    except FileNotFoundError as e:
        return (127, "", str(e), None)

    out = proc.stdout or ""
    err = proc.stderr or ""
    detected = _pick_path_from_stdout(out) or _pick_path_from_stdout(err)
    return (proc.returncode, out, err, detected)

def try_one_method(method_path: str, url: str) -> Optional[str]:
    log(f"Selected downloader: {method_path}")
    # Try in-process first
    try:
        mod = import_by_path("yt2audio_method_mod", method_path)
        out_path = call_downloader_module_inprocess(mod, url)
        if out_path:
            return out_path
    except SystemExit:
        pass
    except Exception:
        pass
    # Fallback to CLI
    log("[startgetaudio] Falling back to CLI execution of the method script…")
    code, out, err, detected = run_method_cli(sys.executable, method_path, url, cwd=os.path.dirname(method_path))
    if out.strip():
        print(out, end="" if out.endswith("\n") else "\n")
    if err.strip():
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    if detected and os.path.exists(detected):
        return os.path.abspath(detected)
    return None

# ---------- Main ----------

def main():
    repo_root = repo_root_from_here()
    log("startgetaudio: starting…")
    log(f"repo_root: {repo_root}")

    # 1) Import getlink.py
    getlink_path = find_getlink_py(repo_root)
    if not getlink_path:
        hr()
        log("ERROR: Could not locate getlink.py.")
        log("Looked under youtube2audwstems/ and link2stems/ (repo root & parent).")
        log("==broken==")
        return

    log(f"getlink.py: {getlink_path}")
    try:
        getlink_mod = import_by_path("getlink", getlink_path)
    except Exception as e:
        hr()
        log("ERROR: Failed to import getlink.py")
        log(str(e))
        log(traceback.format_exc())
        log("==broken==")
        return

    # 2) Capture platform + URL
    try:
        platform, url = call_getlink(getlink_mod)
        platform = normalize_platform(platform)
        log(f"Link captured. platform={platform}, url={url}")
    except Exception as e:
        hr()
        log("ERROR: getlink.py did not return a valid link/platform.")
        log(str(e))
        log(traceback.format_exc())
        log("==broken==")
        return

    # 3) Route and run
    out_path: Optional[str] = None
    if platform == "youtube":
        yt_methods = find_youtube_methods(repo_root)
        if not yt_methods:
            hr()
            log("ERROR: No YouTube method scripts found (method1/2/3).")
            log("==broken==")
            return
        errors = []
        for mp in yt_methods:
            out_path = try_one_method(mp, url)
            if out_path:
                break
            else:
                errors.append(f"Failed: {mp}")
        if not out_path:
            hr()
            log("ERROR: All YouTube methods failed.")
            for e in errors:
                log(e)
            log("==broken==")
            return

    elif platform == "instagram":
        method_path = find_instagram_method_py(repo_root)
        if not method_path:
            hr()
            log("ERROR: methods/instagram/instamethod1.py not found.")
            log("==broken==")
            return
        out_path = try_one_method(method_path, url)
        if not out_path:
            hr()
            log("ERROR: Instagram method failed.")
            log("==broken==")
            return
    else:
        hr()
        log(f"ERROR: Unrecognized platform tag: {platform}")
        log("==broken==")
        return

    # 4) Success
    hr()
    log("SUCCESS: Download completed.")
    log(f"File location: {out_path}")
    print(out_path)

    # 5) Return to menu.py
    menu_path = find_menu_py(repo_root)
    if menu_path:
        hr()
        log("Returning to menu…")
        try:
            os.execv(sys.executable, [sys.executable, menu_path])
        except Exception as e:
            log("Failed to reload menu.py automatically; please run it manually.")
            log(str(e))
    else:
        hr()
        log("menu.py not found next to repo root; exiting to shell.")

if __name__ == "__main__":
    main()