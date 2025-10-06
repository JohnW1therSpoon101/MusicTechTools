#!/usr/bin/env python3
"""
start.py  (link2stems pipeline)

Flow:
  1) Use getlink.py to capture (platform, url).
  2) Route to downloader method:
       • YouTube  -> methods/youtube/method1.py → method2.py → method3.py (fallback chain)
       • Instagram-> methods/instagram/instamethod1.py
     Try in-process first; fall back to CLI "<python> method.py <url>".
  3) Detect final audio path from method output (robust parsing).
  4) If audio exists, run details/findtemp.py with that file.
  5) Checkpoint prompt: pick stems method
       1 -> methods/splits/basicsplitter.py
       2 -> methods/splits/splitter.py
  6) Return to menu.py when done.
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

# -------------------- Logging --------------------

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{now()}] {msg}")

def hr() -> None:
    print("-" * 72)

# -------------------- Path helpers --------------------

def repo_root_from_here() -> str:
    here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(here))

def candidate_content_roots(repo_root: str) -> List[str]:
    parent = os.path.dirname(repo_root)
    return [
        os.path.join(repo_root, "youtube2audwstems"),
        os.path.join(repo_root, "link2stems"),
        os.path.join(parent, "youtube2audwstems"),
        os.path.join(parent, "link2stems"),
    ]

def _find_file(repo_root: str, rel_parts: List[str]) -> Optional[str]:
    for root in candidate_content_roots(repo_root):
        p = os.path.join(root, *rel_parts)
        if os.path.isfile(p):
            return p
    return None

def find_getlink(repo_root: str) -> Optional[str]:
    return _find_file(repo_root, ["getlink.py"])

def find_youtube_methods(repo_root: str) -> List[str]:
    paths = []
    for name in ("method1.py", "method2.py", "method3.py"):
        p = _find_file(repo_root, ["methods", "youtube", name])
        if p:
            paths.append(p)
    if not paths:
        p = _find_file(repo_root, ["methods", "method1.py"])
        if p:
            paths.append(p)
    return paths

def find_instagram_method(repo_root: str) -> Optional[str]:
    return _find_file(repo_root, ["methods", "instagram", "instamethod1.py"])

def find_findtemp(repo_root: str) -> Optional[str]:
    return _find_file(repo_root, ["details", "findtemp.py"])

def find_splitter(repo_root: str) -> Optional[str]:
    return _find_file(repo_root, ["methods", "splits", "splitter.py"])

def find_basicsplitter(repo_root: str) -> Optional[str]:
    return _find_file(repo_root, ["methods", "splits", "basicsplitter.py"])

def find_menu(repo_root: str) -> Optional[str]:
    p = os.path.join(repo_root, "menu.py")
    return p if os.path.isfile(p) else None

# -------------------- Import helper --------------------

def import_by_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {module_name} at {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

# -------------------- getlink integration --------------------

def call_getlink(getlink_mod) -> Tuple[str, str]:
    """
    Accepts:
      get_link_info() -> {"platform": "...", "url": "..."} | (platform, url) | JSON str
      get_link()      -> "<url>"  (platform inferred)
      main()/run()    -> any of the above
    Returns (platform, url)
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

# -------------------- Platform detection --------------------

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

# -------------------- Downloader (in-process + CLI fallback) --------------------

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

def _invoke_callable(func, url: str, mod) -> Optional[str]:
    sig = inspect.signature(func)
    required_positionals = [
        p for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.default is inspect._empty
    ]
    if len(required_positionals) >= 1:
        rv = func(url)
        return _normalize_path(rv) or _output_from_module_vars(mod)
    os.environ["YT2AUDIO_URL"] = url
    rv = func()
    return _normalize_path(rv) or _output_from_module_vars(mod)

def call_downloader_inprocess(mod, url: str) -> Optional[str]:
    for fn in ("download_audio", "download", "run", "main"):
        if hasattr(mod, fn):
            try:
                out_path = _invoke_callable(getattr(mod, fn), url, mod)
                if out_path:
                    return os.path.abspath(out_path)
            except Exception:
                continue
    return None

_PATH_RE = re.compile(r'(/[^:\n\r\t]*?\.(?:wav|mp3|m4a|aac|flac|ogg|opus))', re.IGNORECASE)

def _pick_path_from_text(s: str) -> Optional[str]:
    if not s:
        return None
    matches = _PATH_RE.findall(s)
    for cand in reversed(matches):
        p = cand.strip().strip('"').strip("'")
        if os.path.isabs(p) and os.path.exists(p):
            return os.path.abspath(p)
    return None

def run_cli(python_exe: str, script_path: str, url: str, cwd: Optional[str] = None):
    env = os.environ.copy()
    env["YT2AUDIO_URL"] = url
    proc = subprocess.run(
        [python_exe, script_path, url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env,
        check=False
    )
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")

def try_one_method(method_path: str, url: str) -> Optional[str]:
    log(f"Selected downloader: {method_path}")
    # In-process first
    try:
        mod = import_by_path("yt2_method", method_path)
        out_path = call_downloader_inprocess(mod, url)
        if out_path:
            return out_path
    except SystemExit:
        pass
    except Exception:
        pass
    # CLI fallback
    log("[start] Falling back to CLI execution of downloader…")
    code, out, err = run_cli(sys.executable, method_path, url, cwd=os.path.dirname(method_path))
    if out.strip():
        print(out, end="" if out.endswith("\n") else "\n")
    if err.strip():
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    detected = _pick_path_from_text(out) or _pick_path_from_text(err)
    if detected:
        return detected
    return None

# -------------------- Task runners (findtemp + splitters) --------------------

def run_findtemp(findtemp_path: str, audio_path: str) -> None:
    try:
        log(f"Running findtemp.py on: {audio_path}")
        subprocess.run(
            [sys.executable, findtemp_path, audio_path],
            check=False
        )
    except Exception as e:
        log(f"findtemp.py error (continuing): {e}")

def run_splitter(splitter_path: str, audio_path: str) -> None:
    try:
        log(f"[splitter] {os.path.basename(splitter_path)}")
        subprocess.run(
            [sys.executable, splitter_path, audio_path],
            check=False
        )
    except Exception as e:
        log(f"splitter error (continuing): {e}")

# -------------------- Main --------------------

def main():
    log("==insertlink")
    repo_root = repo_root_from_here()

    # 1) Locate and import getlink.py
    try:
        getlink_path = find_getlink(repo_root)
        if not getlink_path:
            raise FileNotFoundError("getlink.py not found in youtube2audwstems/ or link2stems/")
        log("Imported getlink.py successfully.")
        getlink_mod = import_by_path("getlink", getlink_path)
    except Exception as e:
        log("ERROR: Could not import getlink.py")
        log(traceback.format_exc())
        log("==broken==")
        return

    # 2) Capture (platform, url)
    try:
        platform, url = call_getlink(getlink_mod)
        platform = normalize_platform(platform)
    except Exception as e:
        log("ERROR: getlink failed to provide link/platform")
        log(str(e))
        log(traceback.format_exc())
        log("==broken==")
        return

    # 3) Select and run downloader(s)
    audio_path: Optional[str] = None
    if platform == "youtube":
        yt_methods = find_youtube_methods(repo_root)
        if not yt_methods:
            log("ERROR: No YouTube method scripts found (method1/2/3).")
            log("==broken==")
            return
        for mp in yt_methods:
            audio_path = try_one_method(mp, url)
            if audio_path:
                break
        if not audio_path:
            log("Download failed via all YouTube methods")
            log("==broken==")
            return
    elif platform == "instagram":
        method_path = find_instagram_method(repo_root)
        if not method_path:
            log("ERROR: methods/instagram/instamethod1.py not found.")
            log("==broken==")
            return
        audio_path = try_one_method(method_path, url)
        if not audio_path:
            log("Download failed via Instagram method")
            log("==broken==")
            return
    else:
        log(f"ERROR: Unrecognized platform tag: {platform}")
        log("==broken==")
        return

    # 4) Continue pipeline
    log(f"Downloaded audio: {audio_path}")

    findtemp_path = find_findtemp(repo_root)
    if findtemp_path:
        run_findtemp(findtemp_path, audio_path)
    else:
        log("Note: details/findtemp.py not found; skipping tempo analysis.")

    basicsplitter_path = find_basicsplitter(repo_root)
    splitter_path = find_splitter(repo_root)

    if basicsplitter_path or splitter_path:
        hr()
        print("[CHECKPOINT] Choose stem separation:")
        print("  1) Basic Stem Separation")
        print("  2) Complex Stem Separation")
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1" and basicsplitter_path:
            run_splitter(basicsplitter_path, audio_path)
        elif choice == "2" and splitter_path:
            run_splitter(splitter_path, audio_path)
        else:
            log("No valid splitter path for your selection; skipping stem separation.")
    else:
        log("No splitters found; skipping stem separation.")

    # 5) Return to menu
    menu_path = find_menu(repo_root)
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

# ---- support funcs reused above ----

def infer_platform_from_url(url: str) -> str:
    if re.search(r"(youtube\.com|youtu\.be)", url, re.I):
        return "youtube"
    if re.search(r"(instagram\.com)", url, re.I):
        return "instagram"
    return "youtube"

if __name__ == "__main__":
    main()