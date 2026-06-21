"""Locate + load the grounding report — the wire format between producer and consumers.

``grounding_report.json`` is the contract the pytest plugin emits and every consumer reads.
It is a *regenerable projection* of running the claims — never the source of truth (that is
the tests + the source bytes). Delete it and rebuild by re-running pytest.
"""
from __future__ import annotations

import json
from pathlib import Path

GROUNDING_REPORT_NAME = "grounding_report.json"


def load_report(path) -> dict:
    """Parse a grounding_report.json into its dict form (``{"claims": [...]}``)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def claims_of(data: dict) -> list[dict]:
    """The claim records from a loaded report (defensive against a malformed file)."""
    return [c for c in data.get("claims", []) if isinstance(c, dict)]


def find_report(start) -> Path | None:
    """Resolve ``start`` to a grounding_report.json: an existing file is used as-is; a
    directory resolves to ``<dir>/grounding_report.json`` (searching upward a few levels).
    Returns ``None`` if none is found."""
    p = Path(start)
    if p.is_file():
        return p
    if p.is_dir():
        cand = p / GROUNDING_REPORT_NAME
        if cand.is_file():
            return cand
        for parent in list(p.resolve().parents)[:4]:
            cand = parent / GROUNDING_REPORT_NAME
            if cand.is_file():
                return cand
    return None
