"""pytest plugin — capture provenance, collect claims, emit the grounding report.

A *claim* is a pytest test: its :func:`grounding.statement` call is the proposition, its
node id is the stable id, its body is the justification (reads sha-pinned via ``load``/
``doc``), and its assert is the grounding/drift check. Markers carry the non-binary
judgment (``strength``/``caveats``/``kind``/``reviewed``); lifecycle rides pytest states
(``xfail`` = contradicted/retracted, ``skip`` = unverifiable).

This plugin:
  * registers the markers (no "unknown mark" warnings),
  * wraps each test in a :class:`grounding.Capture` (autouse fixture) so every ``load``/
    ``doc`` read is recorded, and installs the bypass guard,
  * collects ``{id, statement, outcome, evidence, inputs+shas, strength, caveats, kind,
    reviewed, notes}`` per claim and writes ``grounding_report.{json,md}``.

Auto-loaded via the ``pytest11`` entry point, so a bare ``pytest`` collects grounded claims
once the package is installed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from . import guard
from ._capture import Capture, _CURRENT, registry

_MARKERS = {
    "strength": "strength(level): how strongly the evidence supports the statement",
    "caveats": "caveats(text): scope/limits to keep in mind",
    "kind": "kind(category): result|design|external|interpretive|...",
    "reviewed": "reviewed(**verdict): a reviewer's support judgment of the claim",
}


def pytest_addoption(parser):
    g = parser.getgroup("grounding")
    g.addoption("--grounding-out", action="store", default=None,
                help="directory for grounding_report.{json,md} (default: rootdir)")
    g.addoption("--grounding-fresh", "--no-merge", action="store_true", default=False,
                dest="grounding_fresh",
                help="ignore any existing grounding_report.json and write ONLY this run's "
                     "records (clean slate). Default MERGES this run's claims into the "
                     "existing report at test-file granularity, so a partial run updates "
                     "just its own files and leaves other modules' claims intact.")


def pytest_configure(config):
    for name, help_ in _MARKERS.items():
        config.addinivalue_line("markers", help_)
    # Flag untracked reads under the grounding root: GROUNDING_ROOT, else the rootdir.
    guard.set_root(os.environ.get("GROUNDING_ROOT") or str(config.rootpath))
    guard.install_guard()
    config._grounding_records = []


# --------------------------------------------------------------------------- #
# Per-claim capture
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _grounding_capture(request):
    """Set a fresh capture for each claim and attach it to the item so the report hook can
    read it."""
    cap = Capture(claim_id=request.node.nodeid)
    token = _CURRENT.set(cap)
    request.node._grounding_cap = cap
    try:
        yield cap
    finally:
        _CURRENT.reset(token)


def _marker_val(item, name, default=None):
    m = item.get_closest_marker(name)
    if m is None:
        return default
    return m.args[0] if m.args else default


def _marker_kwargs(item, name):
    m = item.get_closest_marker(name)
    return dict(m.kwargs) if m is not None else None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if rep.when != "call":
        return
    cap = getattr(item, "_grounding_cap", None)

    outcome = rep.outcome
    if hasattr(rep, "wasxfail"):
        outcome = "xpass" if rep.passed else "xfail"
    elif rep.skipped and call.excinfo and call.excinfo.errisinstance(pytest.xfail.Exception):
        outcome = "xfail"

    notes = (item.function.__doc__ or "").strip() if hasattr(item, "function") else ""
    statement = cap.statement if cap and cap.statement else None
    evidence = dict(cap.evidence) if cap else {}
    inputs = list(cap.inputs) if cap else []

    advisories: list[str] = []
    if statement is None and outcome not in ("skipped",):
        advisories.append("no statement() — the proposition isn't recorded")
    if cap and cap.bypassed:
        advisories.append(f"{len(cap.bypassed)} untracked read(s) caught by the bypass guard")

    rec = {
        "id": item.nodeid,
        "statement": statement,
        "notes": notes or None,
        "outcome": outcome,
        "kind": _marker_val(item, "kind", "unspecified"),
        "strength": _marker_val(item, "strength", "unspecified"),
        "caveats": _marker_val(item, "caveats"),
        "reviewed": _marker_kwargs(item, "reviewed"),
        "evidence": evidence,
        "inputs": inputs,
        "bypassed": list(cap.bypassed) if cap else [],
        "advisories": advisories,
        "longrepr": str(rep.longrepr) if rep.failed and not getattr(rep, "wasxfail", None) else None,
    }
    item.config._grounding_records.append(rec)
    registry[item.nodeid] = rec  # enables uses(claim_id) for later claims


# --------------------------------------------------------------------------- #
# Report emission
# --------------------------------------------------------------------------- #
def _json_default(o):
    if hasattr(o, "item"):           # numpy scalar -> python scalar
        try:
            return o.item()
        except (ValueError, TypeError):
            pass
    if hasattr(o, "tolist"):         # numpy array / pandas Index/Series -> list
        return o.tolist()
    return str(o)


_OUTCOME_LABEL = {
    "passed": "✅ grounded", "failed": "❌ DRIFT", "xfail": "⊘ contradicted",
    "xpass": "⚠️ unexpectedly grounded", "skipped": "… unverifiable",
}


def _test_file_of(record: dict) -> str:
    cid = record.get("id") or ""
    head = cid.split("::", 1)[0]
    return Path(head).name or cid


def _merge_records(prior: list[dict], current: list[dict]) -> list[dict]:
    """Union prior and current records at test-file granularity, sorted by id: drop prior
    records from files this run produced, keep the rest, add this run's records. A
    whole-suite run replaces everything; a one-file run updates just that file."""
    current_files = {_test_file_of(r) for r in current}
    kept = [r for r in prior if _test_file_of(r) not in current_files]
    return sorted(kept + list(current), key=lambda r: r.get("id") or "")


def _load_prior_records(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [c for c in data.get("claims", []) if isinstance(c, dict)]
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def pytest_sessionfinish(session):
    config = session.config
    records = getattr(config, "_grounding_records", [])
    if not records:
        return
    out_dir = Path(config.getoption("--grounding-out") or config.rootpath)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "grounding_report.json"

    if config.getoption("grounding_fresh", default=False):
        merged = sorted(records, key=lambda r: r.get("id") or "")
    else:
        merged = _merge_records(_load_prior_records(json_path), records)

    json_path.write_text(
        json.dumps({"claims": merged}, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8")
    (out_dir / "grounding_report.md").write_text(_render_md(merged), encoding="utf-8")
    config._grounding_report_path = out_dir / "grounding_report.md"


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    p = getattr(config, "_grounding_report_path", None)
    if p is not None:
        terminalreporter.write_sep("-", "grounding report")
        terminalreporter.write_line(f"  {p}")


def _render_md(records: list[dict]) -> str:
    from collections import Counter

    tally = Counter(r["outcome"] for r in records)
    lines = ["# Grounding report", "", "| outcome | n |", "|---|---|"]
    for k, v in tally.items():
        lines.append(f"| {_OUTCOME_LABEL.get(k, k)} | {v} |")
    lines.append("")
    by_kind: dict[str, list[dict]] = {}
    for r in records:
        by_kind.setdefault(r["kind"], []).append(r)
    for kind in sorted(by_kind):
        lines += [f"## kind: {kind}", ""]
        for r in by_kind[kind]:
            lines.append(f"### {_OUTCOME_LABEL.get(r['outcome'], r['outcome'])} — `{r['id'].split('::')[-1]}`")
            if r.get("statement"):
                lines.append(f"> {r['statement']}")
            meta = f"**strength:** {r['strength']}"
            if r.get("caveats"):
                meta += f" · **caveats:** {r['caveats']}"
            lines += ["", meta]
            if r.get("evidence"):
                ev = ", ".join(f"`{k}={v}`" for k, v in r["evidence"].items())
                lines.append(f"\n**evidence:** {ev}")
            if r.get("inputs"):
                lines.append("\n**inputs:**")
                for i in r["inputs"]:
                    via = "" if i["via"] == "tracked" else f" _({i['via']})_"
                    lines.append(f"- `{i['kind']}` {Path(i['path']).name} — `{i['sha256'][:12]}`{via}")
            if r.get("advisories"):
                lines.append("\n**advisories:** " + "; ".join(r["advisories"]))
            if r.get("longrepr"):
                lines.append(f"\n```\n{r['longrepr'][:800]}\n```")
            lines.append("")
    return "\n".join(lines) + "\n"
