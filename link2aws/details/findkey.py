#!/usr/bin/env python3
"""
details/findkey.py

Determine the musical key of an audio file using Essentia's KeyExtractor.

Usage:
    python details/findkey.py /path/to/audio.wav
    python details/findkey.py /path/to/audio.wav --quiet
    python details/findkey.py --help

Output (stdout):
    Key = D minor
"""

import argparse
import os
import sys

# Try to use the project's logger if available.
try:
    from check import log  # yt2aws/check.py should expose log(msg: str)
except Exception:
    def log(msg: str):
        print(msg, flush=True)

def _import_essentia():
    try:
        import essentia
        from essentia.standard import MonoLoader, KeyExtractor
        return essentia, MonoLoader, KeyExtractor
    except Exception as e:
        raise RuntimeError(
            "Essentia is required but not installed or failed to import.\n"
            "Try: pip install essentia\n"
            "More installation options: https://essentia.upf.edu/installation.html\n"
            f"Original error: {e}"
        )

def detect_key(audio_path: str, sample_rate: int | None = None):
    """
    Returns (key_string, scale_string, strength_float).
    Example: ('D', 'minor', 0.78)
    """
    _, MonoLoader, KeyExtractor = _import_essentia()

    if sample_rate is None:
        # Let Essentia use the file's native rate.
        loader = MonoLoader(filename=audio_path)
    else:
        loader = MonoLoader(filename=audio_path, sampleRate=sample_rate)

    audio = loader()

    # KeyExtractor outputs: key (e.g. 'D'), scale ('major'/'minor'), strength (0..1)
    key, scale, strength = KeyExtractor()(audio)
    return key, scale, strength

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Find the musical key of an audio file using Essentia."
    )
    parser.add_argument("input", help="Path to audio file (wav/mp3/aiff/flac, etc.)")
    parser.add_argument(
        "--sr",
        type=int,
        default=None,
        help="Optional resample rate (e.g., 44100). If omitted, use file's native rate."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final 'Key = ...' line to stdout."
    )

    args = parser.parse_args(argv)

    audio_path = os.path.abspath(args.input)
    if not os.path.isfile(audio_path):
        log(f"[findkey] File not found: {audio_path}")
        sys.exit(2)

    try:
        if not args.quiet:
            log(f"[findkey] Analyzing: {audio_path}")
            if args.sr:
                log(f"[findkey] Using sample rate: {args.sr} Hz")

        key, scale, strength = detect_key(audio_path, sample_rate=args.sr)

        # Required final output format:
        print(f"Key = {key} {scale}")

        if not args.quiet:
            # Extra context to stderr via log (doesn't affect required stdout line)
            log(f"[findkey] Confidence: {strength:.2f}")

        return 0

    except RuntimeError as e:
        # Dependency or import error
        log(f"[findkey][ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        log(f"[findkey][ERROR] Unexpected failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())