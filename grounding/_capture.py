"""The capture context — the heart of automatic provenance.

While a claim runs, a :class:`Capture` is active in a context variable. Every tracked read
(``load``/``data``/``doc``, or an untracked read the bypass guard catches) records its
``{kind, path, sha256}`` into it, and the claim's :func:`grounding.statement` /
:func:`grounding.evidence` write the proposition + headline numbers. A claim's id + its
captured inputs + its statement + its evidence form a *computed* record — never
hand-maintained.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

# Source-file kinds we consider "tracked": reading one while a capture is active is
# provenance the claim depends on. The bypass guard watches the same set.
TRACKED_SUFFIXES = {
    ".csv", ".tsv", ".xlsx", ".xls", ".pdf", ".docx", ".pptx", ".ppt",
    ".json", ".yaml", ".yml",
}


@dataclass
class Capture:
    """Records every tracked source read + the statement and headline numbers for one
    claim. The claim's id, captured inputs, statement and evidence are all computed from
    what actually ran, so they can't drift from reality."""

    claim_id: str | None = None
    statement: str | None = None                       # the proposition (set by statement())
    inputs: list[dict] = field(default_factory=list)   # {kind, path, sha256, via}
    evidence: dict[str, Any] = field(default_factory=dict)
    bypassed: list[str] = field(default_factory=list)  # untracked reads the guard caught
    _seen: set = field(default_factory=set)

    def record(self, kind: str, path, sha: str, via: str = "tracked") -> None:
        key = (kind, str(path))
        if key in self._seen:
            return
        self._seen.add(key)
        self.inputs.append({"kind": kind, "path": str(path), "sha256": sha, "via": via})

    def merge(self, other: "Capture") -> None:
        """Pull another capture's inputs in transitively (used by :func:`grounding.uses`)."""
        for inp in other.inputs:
            self.record(inp["kind"], inp["path"], inp["sha256"], via="uses")


_CURRENT: contextvars.ContextVar[Capture | None] = contextvars.ContextVar(
    "grounding_capture", default=None)


def current_capture() -> Capture | None:
    return _CURRENT.get()


def record(kind: str, path, sha: str, via: str = "tracked") -> None:
    """Record a (kind, path, sha) into the active capture, if any. Called by the tracked
    loaders and the bypass guard."""
    cap = _CURRENT.get()
    if cap is not None:
        cap.record(kind, path, sha, via)


# A session-wide registry of completed claim records, keyed by node id. Populated by the
# plugin so :func:`grounding.uses` can pull a prior claim's evidence + inputs.
registry: dict[str, dict] = {}
