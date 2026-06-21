"""grounding — turn assertions about data into re-runnable, provenance-tracked claims.

A claim is a pytest test. Inside it you ground a statement in sha-pinned evidence:

    from grounding import data, doc, statement, evidence, strength, caveats

    @strength("strong")
    @caveats("single run; n=3 per dose")
    def test_knockdown_at_high_dose():
        df = data("measurements.csv")            # sha-pinned read, recorded as provenance
        hi = df[df.dose == 300].knockdown.mean()
        statement(f"Knockdown reached {hi:.0f}% at the 300 nM dose")   # the proposition
        evidence(knockdown_pct=round(hi, 1))
        assert hi > 50                           # the grounding/drift check

The pytest plugin (auto-loaded via the ``pytest11`` entry point) wraps each test in a
capture, records every ``data``/``doc`` read, and emits ``grounding_report.json``. The
non-binary judgment (``@strength``/``@caveats``/``@kind``/``@reviewed``) is metadata a
reviewer judges — never a pass/fail input.

Everything here is a pure function of file bytes: no network, no key, no model.

Public API:

    data / load        sha-pinned CSV loader -> DataFrame(.attrs)        [needs the [data] extra]
    doc -> DocRef      record a document; DocRef.contains() verifies a quote [needs [docs]]
    statement(text)    the claim's proposition (ideally computed from data)
    evidence(**kv)     headline numbers for the report
    uses(claim_id)     compose on a prior claim (transitive provenance + evidence)
    strength/caveats/kind/reviewed   the judgment markers
    Capture / current_capture / record / registry / TRACKED_SUFFIXES   the capture core
    install_guard      install the untracked-read bypass guard (the plugin does this)
"""
from __future__ import annotations

from ._capture import (
    Capture,
    TRACKED_SUFFIXES,
    current_capture,
    record,
    registry,
)
from ._text import match_phrase, sha256
from .loaders import (
    DocRef,
    EmptyExtraction,
    UnsupportedDocFormat,
    data,
    doc,
    load,
)
from .claim import caveats, evidence, kind, reviewed, statement, strength, uses
from .guard import install_guard

__all__ = [
    "load", "data", "doc", "DocRef", "UnsupportedDocFormat", "EmptyExtraction",
    "statement", "evidence", "uses",
    "strength", "caveats", "kind", "reviewed",
    "Capture", "current_capture", "record", "registry", "TRACKED_SUFFIXES",
    "match_phrase", "sha256",
    "install_guard",
]

__version__ = "0.0.1"
