"""Trace — re-verify a report's claims still rest on the bytes they recorded.

For each claim in a grounding_report.json, re-hash every recorded input and compare to the
stored sha256. A claim is GROUNDED if every input still exists and matches; a changed or
missing input is a break. This is the static, git-free check that answers "is this
conclusion still grounded?" without re-running the suite. (Re-running the suite is the
*executable* complement — it recomputes the claim against the current bytes.)
"""
from __future__ import annotations

from pathlib import Path

from ._text import sha256
from .report_io import claims_of, find_report, load_report


def trace(report_path) -> dict:
    """Walk every claim's recorded inputs and re-verify their shas. Returns
    ``{status, report, claims:[{id, statement, outcome, breaks:[...]}]}`` where ``status``
    is ``GROUNDED`` iff no claim has a break."""
    rp = find_report(report_path)
    if rp is None:
        return {"status": "NO_REPORT", "report": str(report_path), "claims": []}

    claims = claims_of(load_report(rp))
    base = rp.parent
    out = []
    status = "GROUNDED"
    for c in claims:
        breaks: list[str] = []
        for inp in c.get("inputs", []):
            p = Path(inp["path"])
            if not p.is_absolute():
                p = base / p
            if not p.is_file():
                breaks.append(f"missing: {inp['path']}")
                continue
            if sha256(p.read_bytes()) != inp.get("sha256"):
                breaks.append(f"changed: {inp['path']}")
        # A claim that recorded no inputs at all can't be grounded in anything.
        if not c.get("inputs"):
            breaks.append("no recorded inputs")
        if breaks:
            status = "BROKEN"
        out.append({
            "id": c.get("id"),
            "statement": c.get("statement"),
            "outcome": c.get("outcome"),
            "breaks": breaks,
        })
    return {"status": status, "report": str(rp), "claims": out}


def render(result: dict) -> str:
    """Human-readable trace summary."""
    lines = [f"trace: {result['status']}  ({result['report']})"]
    for c in result["claims"]:
        mark = "✅" if not c["breaks"] else "❌"
        name = (c["id"] or "").split("::")[-1]
        lines.append(f"  {mark} {name}")
        if c.get("statement"):
            lines.append(f"       {c['statement']}")
        for b in c["breaks"]:
            lines.append(f"       ! {b}")
    return "\n".join(lines)
