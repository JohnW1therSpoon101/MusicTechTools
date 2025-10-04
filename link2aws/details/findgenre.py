#!/usr/bin/env python3
"""
findgenre.py — Lightweight genre *bucket* guesser using librosa features.

Outputs (machine-readable on stdout):
  GENRE: <label>
  BPM_WINDOW: <min> <max>

Buckets + windows (tweak as you like):
  - rnb_hiphop    -> 70–100
  - pop           -> 90–130
  - house         -> 118–128
  - edm           -> 120–140
  - trap_halftime -> 130–160 (often feels like 65–80)
  - ballad        -> 60–80
  - unknown       -> 70–100 (fallback)

This is intentionally simple (rule-based) so it runs anywhere with librosa.
"""

import sys
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import librosa

# ---- Tunable mapping ----
GENRE_TO_WINDOW = {
    "rnb_hiphop":    (70, 100),
    "pop":           (90, 130),
    "house":         (118, 128),
    "edm":           (120, 140),
    "trap_halftime": (130, 160),  # musical feel ~65–80
    "ballad":        (60, 80),
    "unknown":       (70, 100),
}

def summarize_features(y: np.ndarray, sr: int) -> dict:
    # Percussive emphasis
    y_h, y_p = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_p, sr=sr)
    tempo_guess = float(librosa.beat.tempo(onset_envelope=onset_env, sr=sr, aggregate="median"))

    cent = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85).mean()
    zcr = librosa.feature.zero_crossing_rate(y).mean()

    # Chroma energy balance (harmonic content)
    chroma = librosa.feature.chroma_cqt(y=y_h, sr=sr)
    chroma_var = np.var(chroma, axis=1).mean()

    # Percussive ratio
    percussive_ratio = float(np.mean(np.abs(y_p)) / (np.mean(np.abs(y)) + 1e-9))

    # Tempogram clarity (periodicity strength)
    tg = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
    clarity = float(np.max(np.mean(tg, axis=1)))  # higher = clearer periodicity

    return {
        "tempo_guess": tempo_guess,
        "centroid": cent,
        "rolloff": rolloff,
        "zcr": zcr,
        "chroma_var": chroma_var,
        "perc_ratio": percussive_ratio,
        "clarity": clarity,
    }

def rule_based_bucket(f: dict) -> str:
    t = f["tempo_guess"]
    cent = f["centroid"]
    roll = f["rolloff"]
    zcr = f["zcr"]
    perc = f["perc_ratio"]
    clar = f["clarity"]
    cvar = f["chroma_var"]

    # Very slow + harmonic/low-brightness -> ballad
    if t < 85 and cent < 2000 and roll < 4000 and perc < 0.35:
        return "ballad"

    # House pocket: tight periodicity + tempo in range
    if 115 <= t <= 132 and clar > 0.2 and perc >= 0.4:
        # narrower "classic" house lane
        if 118 <= t <= 128:
            return "house"
        return "edm"

    # Trap/halftime cues: high tempo guess, but low percussive ratio and lower brightness
    if t >= 130 and perc < 0.45 and cent < 3500:
        return "trap_halftime"

    # Pop: mid brightness + clear periodicity + mid tempo
    if 90 <= t <= 130 and cent >= 2000 and clar > 0.15:
        return "pop"

    # R&B/Hip-hop: moderate or low tempo, lower brightness, strong percussive onsets
    if 70 <= t <= 105 and cent < 3000 and perc >= 0.35:
        return "rnb_hiphop"

    # EDM-ish bright, punchy, faster
    if t >= 120 and (cent >= 3000 or roll >= 6000) and perc >= 0.35:
        return "edm"

    return "unknown"

def pick_window(genre: str) -> Tuple[float, float]:
    return GENRE_TO_WINDOW.get(genre, GENRE_TO_WINDOW["unknown"])

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: findgenre.py <audio_path>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).expanduser()
    if not path.exists():
        print(f"[error] File not found: {path}", file=sys.stderr)
        return 2

    try:
        y, sr = librosa.load(str(path), mono=True)
        # quick trim to reduce intro/outro noise influence
        y, _ = librosa.effects.trim(y, top_db=30)
        feats = summarize_features(y, sr)
        genre = rule_based_bucket(feats)
        lo, hi = pick_window(genre)
    except Exception as e:
        print(f"[error] Genre analysis failed: {e}", file=sys.stderr)
        return 1

    print(f"GENRE: {genre}")
    print(f"BPM_WINDOW: {lo} {hi}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())