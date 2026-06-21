"""The claim surface: the proposition, the evidence, composition, and the judgment markers.

A claim is a pytest test. Inside it:

    statement(...)              the proposition — what is asserted (ideally computed from data)
    evidence(**kv)              headline numbers, kept OUT of the assert
    uses(claim_id)              compose on a prior claim (transitive provenance + its evidence)

and on it, the non-binary judgment (metadata, never a pass/fail input):

    @strength(...) @caveats(...) @kind(...) @reviewed(...)
"""
from __future__ import annotations

from ._capture import current_capture, registry


def statement(text: str) -> None:
    """Record the claim's proposition — the human-readable statement a reviewer judges and
    a citation renders. Prefer a value computed from the data, e.g.
    ``statement(f"knockdown reached {hi:.0f}% at the high dose")``, so the claim literally
    cannot state a number its evidence doesn't produce. One statement per claim."""
    cap = current_capture()
    if cap is not None:
        cap.statement = str(text)


def evidence(**kv) -> None:
    """Record headline numbers for the report (e.g. ``evidence(knockdown_pct=53)``). Kept
    *out* of the assert so the assertion stays a pure grounding/drift check."""
    cap = current_capture()
    if cap is not None:
        cap.evidence.update(kv)


def uses(claim_id: str) -> dict:
    """Compose on another claim: merge its recorded inputs into this capture (transitive
    provenance) and return its evidence dict. The referenced claim must have run earlier in
    the session (collection order).

    ``claim_id`` may be a full node id or a bare function name. A bare name that is ambiguous
    across files prefers a candidate in the *calling claim's own file*; for a genuine
    cross-file reference, pass a qualified id (``"<file>::test_x"``)."""
    cap = current_capture()
    rec = registry.get(claim_id)
    if rec is None:
        cand = [k for k in registry
                if k == claim_id or k.endswith("::" + claim_id) or k.split("::")[-1] == claim_id]
        if len(cand) > 1 and cap is not None and cap.claim_id:
            my_file = cap.claim_id.split("::")[0]
            same = [k for k in cand if k.split("::")[0] == my_file]
            if same:
                cand = same
        if len(cand) == 1:
            rec = registry.get(cand[0])
        elif len(cand) > 1:
            raise LookupError(
                f"uses({claim_id!r}) is ambiguous — qualify it as "
                f"'<file>::{claim_id.split('::')[-1]}'. Candidates: {sorted(cand)}")
    if rec is None:
        raise LookupError(
            f"uses({claim_id!r}): no completed claim with that id has run yet "
            f"(known: {sorted(registry)})")
    if cap is not None:
        for inp in rec["inputs"]:
            cap.record(inp["kind"], inp["path"], inp["sha256"], via="uses")
    return dict(rec.get("evidence", {}))


# --------------------------------------------------------------------------- #
# Markers — the non-binary judgment, kept out of the assert.
# --------------------------------------------------------------------------- #
def _marker(name):
    import pytest
    return getattr(pytest.mark, name)


def strength(level: str):
    """``@strength("strong|moderate|weak|...")`` — how strongly the evidence supports the
    statement. Metadata, not a pass/fail input; edits across commits are the
    belief-change ledger."""
    return _marker("strength")(level)


def caveats(text: str):
    """``@caveats("...")`` — scope/limits a reader must keep in mind."""
    return _marker("caveats")(text)


def kind(category: str):
    """``@kind("result|design|external|interpretive|...")`` — what sort of assertion this is."""
    return _marker("kind")(category)


def reviewed(**verdict):
    """``@reviewed(by=..., support=True, date=..., note=...)`` — a reviewer's (human or
    fresh-context agent) one-time judgment that the evidence actually supports the
    statement as worded. The mechanical check is the assert; this records the reading
    judgment that the assert can't make. ``support=False`` flags a claim the reviewer
    judged unsupported."""
    return _marker("reviewed")(**verdict)
