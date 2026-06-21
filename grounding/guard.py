"""Bypass guard — make untracked source reads visible.

While a capture is active we wrap ``pandas.read_csv`` and ``builtins.open`` so a *direct*
read of a tracked source file (one not routed through :func:`grounding.load` / :func:`doc`)
is still captured and flagged. This guarantees the captured input set is complete: a claim
can't quietly read a CSV behind the harness's back. We capture-and-flag rather than
hard-fail, so the grounding report still renders and the flag surfaces in the claim record.

Only reads of tracked-suffix files *under the grounding root* are considered — the root is
``GROUNDING_ROOT`` (env) or whatever the plugin sets to the pytest rootdir — so the guard
never interferes with the test runner reading its own internals or temp files.
"""
from __future__ import annotations

import builtins
import os
from pathlib import Path

from ._capture import TRACKED_SUFFIXES, current_capture
from ._text import sha256

_guard_installed = False
_orig_open = builtins.open
_orig_read_csv = None
_ROOT: Path | None = None


def set_root(path) -> None:
    """Set the directory under which untracked reads are flagged (the plugin calls this with
    ``GROUNDING_ROOT`` or the pytest rootdir). ``None`` disables flagging."""
    global _ROOT
    _ROOT = Path(path).resolve() if path else None


def _data_root() -> Path | None:
    if _ROOT is not None:
        return _ROOT
    r = os.environ.get("GROUNDING_ROOT")
    return Path(r).resolve() if r else None


def _under_root(p: Path) -> bool:
    root = _data_root()
    if root is None:
        return False
    try:
        p.resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def _maybe_flag(path, via: str) -> None:
    cap = current_capture()
    if cap is None:
        return
    try:
        p = Path(path)
    except TypeError:
        return
    if p.suffix.lower() not in TRACKED_SUFFIXES or not _under_root(p):
        return
    if not p.is_file():
        return
    # If a tracked loader already recorded this exact path, nothing to flag.
    if any(inp["path"] == str(p) for inp in cap.inputs):
        return
    sha = sha256(p.read_bytes())
    cap.record("bypass", p, sha, via=f"bypass:{via}")
    cap.bypassed.append(f"{via}: {p}")


def install_guard() -> None:
    """Patch ``builtins.open`` (always) and ``pandas.read_csv`` (if pandas is installed) to
    flag untracked tracked-file reads. Idempotent; a no-op when no capture is active, so it
    is safe to leave installed for the whole session."""
    global _guard_installed, _orig_read_csv
    if _guard_installed:
        return

    def guarded_open(file, mode="r", *a, **k):
        if "r" in mode and isinstance(file, (str, os.PathLike)):
            _maybe_flag(file, "open")
        return _orig_open(file, mode, *a, **k)

    builtins.open = guarded_open

    try:
        import pandas as pd
    except ImportError:
        pd = None
    if pd is not None:
        orig_read_csv = pd.read_csv
        _orig_read_csv = orig_read_csv

        def guarded_read_csv(*a, **k):
            # Only path-like first args are real file reads; BytesIO (our load()) is skipped.
            target = a[0] if a else k.get("filepath_or_buffer")
            if isinstance(target, (str, os.PathLike)):
                _maybe_flag(target, "pandas.read_csv")
            return orig_read_csv(*a, **k)

        pd.read_csv = guarded_read_csv

    _guard_installed = True
