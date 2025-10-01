#!/usr/bin/env python3
# yt2aws/check.py
"""
Checks & installs dependencies listed in requirements.txt.
- Detect OS (Mac/Windows) and log it.
- For each requirement:
  * If it's a known CLI tool (yt-dlp, ffmpeg, demucs), find with `shutil.which` & log path.
  * Else treat as a Python package, try to import, else mark missing.
- Attempt to install missing Python packages via pip.
- If anything fails, print a detailed log and exit(1).
- If all succeeded, print "DONE!" and exit(0).
"""

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path
from importlib import import_module

LOG = []
SEARCHED_PATHS = os.environ.get("PATH", "").split(os.pathsep)

CLI_TOOLS = {"yt-dlp", "ffmpeg", "demucs"}

def log(line: str):
    print(line, flush=True)
    LOG.append(line)

def hr():
    log("-" * 60)

def detect_os() -> str:
    sysname = platform.system().lower()
    if "windows" in sysname:
        return "Windows"
    if "darwin" in sysname or "mac" in sysname:
        return "Mac"
    return "Other"

def load_requirements(root: Path) -> list[str]:
    req = root / "requirements.txt"
    if not req.exists():
        return []
    lines = []
    for raw in req.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        # strip version specifiers for detection; keep original for install
        lines.append(s)
    return lines

def is_cli_tool(name: str) -> bool:
    base = name.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0]
    return base in CLI_TOOLS

def py_mod_from_req(req: str) -> str:
    # naive mapping: package[extra]==ver → package
    base = req.split("==")[0].split(">=")[0].split("<=")[0]
    base = base.split("[")[0]
    # simple aliasing for common mismatches
    alias = {
        "yt-dlp": "yt_dlp",
        "opencv-python": "cv2",
        "soundfile": "soundfile",
        "torchaudio": "torchaudio",
        "torch": "torch",
        "ffmpeg-python": "ffmpeg",
        "selenium": "selenium",
        "webdriver-manager": "webdriver_manager",
        "demucs": "demucs",
    }
    return alias.get(base, base.replace("-", "_"))

def check_cli(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    if path:
        return True, f"{name} ==> Found ({path})"
    searched = "\n      ".join(SEARCHED_PATHS)
    return False, f"{name} ==> !MIA! (searched PATH entries below)\n      {searched}"

def check_py(req: str) -> tuple[bool, str]:
    mod = py_mod_from_req(req)
    try:
        import_module(mod)
        return True, f"{req} ==> Found (python import '{mod}')"
    except Exception as e:
        return False, f"{req} ==> !MIA! (python import '{mod}' failed: {e})"

def main():
    root = Path(__file__).resolve().parent
    os_label = detect_os()

    hr()
    log(f"OS: {os_label}")
    hr()

    reqs = load_requirements(root)
    if not reqs:
        log("No requirements.txt found or it's empty. Nothing to check.")
        print("DONE!")
        sys.exit(0)

    missing_cli: list[str] = []
    missing_py: list[str] = []

    log("Scanning dependencies declared in requirements.txt ...")
    for req in reqs:
        base = req.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0]
        if is_cli_tool(base):
            ok, msg = check_cli(base)
            log(msg)
            if not ok:
                missing_cli.append(base)
        else:
            ok, msg = check_py(req)
            log(msg)
            if not ok:
                missing_py.append(req)

    hr()
    if missing_cli or missing_py:
        if missing_cli:
            log("CLI tools missing (install these using your OS package manager):")
            for m in missing_cli:
                if os_label == "Mac":
                    hint = f"brew install {m}"
                elif os_label == "Windows":
                    hint = f"winget install {m}"
                else:
                    hint = f"Install {m} for your OS"
                log(f"  - {m}  (e.g., {hint})")
        if missing_py:
            log("Attempting to install missing Python packages via pip:")
            try:
                # Install only the missing python packages (keep version specifiers)
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", *missing_py], check=True)
                log("Python package installation complete. Re-checking imports...")
                # Re-check
                re_missing = []
                for req in missing_py:
                    ok, msg = check_py(req)
                    log(msg)
                    if not ok:
                        re_missing.append(req)
                if re_missing:
                    hr()
                    log("ERROR: Some Python deps are still missing after install:")
                    for r in re_missing:
                        log(f"  - {r}")
                    hr()
                    sys.exit(1)
            except subprocess.CalledProcessError as e:
                hr()
                log("ERROR: pip install failed.")
                log(f"DETAILS:\n{e}")
                hr()
                sys.exit(1)

        # If CLI tools are still missing, fail (we won't auto-install OS tools)
        if missing_cli:
            hr()
            log("ERROR: One or more CLI tools are missing. Install them, then re-run:")
            for m in missing_cli:
                log(f"  - {m}")
            hr()
            sys.exit(1)

    log("All dependencies OK.")
    print("DONE!")
    sys.exit(0)

if __name__ == "__main__":
    main()