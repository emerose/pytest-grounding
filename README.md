# grounding

**Turn assertions about data into re-runnable, provenance-tracked claims — written and reviewed by agents.**

`grounding` is a small runtime on top of pytest. A test stops being a pass/fail check on your *code* and becomes a **grounded claim**: a statement about data, automatically pinned to the exact bytes it depends on, re-checked whenever those bytes change, carrying a non-binary judgment (how strong, with what caveats) that lives in version control.

It's built for a workflow where **an agent writes the claims and a second, fresh-context agent reviews them.**

```bash
pip install grounding            # core (statement-only / quote-only)
pip install 'grounding[data]'    # + CSV grounding via data()/load()
pip install 'grounding[docs]'    # + document quote verification via doc()
```

No network, no API keys, no model inside. Everything is a pure function of file bytes.

## Why agents, specifically

When an agent asserts *"knockdown reached 53% at the high dose,"* you have two questions: **is it mechanically true** against the data, and **does the evidence actually support the claim** as worded? `grounding` splits those, and each half lands with the right reviewer:

- **The mechanical half is the test.** Re-run it; it passes or fails against sha-pinned bytes. No reviewer judgment needed — CI does it.
- **The judgment half is metadata** (`statement`, `@strength`, `@caveats`, the cited quote). A fresh-context reviewer agent reads *exactly* the bytes the author grounded — same shas, no drift — and decides whether the framing is honest.

`grounding_report.json` is the machine-readable handoff: the author agent emits it, the reviewer agent consumes it.

## A claim is a pytest test

```python
from grounding import data, evidence, statement, strength, caveats, kind
from scipy import stats

@kind("result")
@strength("moderate")
@caveats("n=8 per arm, single cohort; not corrected for multiple endpoints")
def test_treatment_lowers_biomarker_vs_vehicle():
    """Serum biomarker at day 28: 10 mg/kg arm vs vehicle, cohort B.

    Reviewer notes: groups are the prespecified arms; Welch's t-test because the
    vehicle arm's spread is larger; two treated animals were excluded upstream for
    dosing errors (already applied in the tidy table).
    """
    df = data("biomarker_day28.csv")
    treated = df[df.arm == "10mpk"].biomarker
    vehicle = df[df.arm == "vehicle"].biomarker

    drop = 1 - treated.mean() / vehicle.mean()
    t, p = stats.ttest_ind(treated, vehicle, equal_var=False)

    statement(f"At day 28, the 10 mg/kg arm showed a {drop:.0%} lower serum biomarker "
              f"than vehicle (Welch t = {t:.1f}, p = {p:.3f}).")
    evidence(pct_drop=round(drop * 100, 1), p_value=round(p, 4))

    assert p < 0.05 and drop > 0    # the qualitative claim: a real, downward effect
```

The three layers don't repeat each other:

- **`statement()`** is the proposition, with numbers interpolated from the data — it *can't* claim a drop the table doesn't produce.
- the **docstring** is the *why and how* — context that lets a later reviewer judge the claim without re-deriving it.
- the **`assert`** guards only the qualitative shape (significant, downward); the quantity lives in the computed statement.

Run it:

```bash
pytest --grounding-out ./out
```

→ `out/grounding_report.json`:

```json
{
  "claims": [{
    "id": "test_efficacy.py::test_treatment_lowers_biomarker_vs_vehicle",
    "statement": "At day 28, the 10 mg/kg arm showed a 41% lower serum biomarker than vehicle (Welch t = 3.2, p = 0.006).",
    "kind": "result",
    "strength": "moderate",
    "caveats": "n=8 per arm, single cohort; not corrected for multiple endpoints",
    "inputs": [{"kind": "data", "path": "biomarker_day28.csv", "sha256": "a17b…", "via": "tracked"}],
    "evidence": {"pct_drop": 41.2, "p_value": 0.0061}
  }]
}
```

Nobody hand-wrote that provenance. `data()` recorded the read; the capture context attached it to the claim.

## Grounding a quote in a document

```python
from grounding import doc, statement

def test_summary_states_endpoint_met():
    """Quote is from the signed CSR §10.1, not the synopsis."""
    csr = doc("clinical_summary.pdf")          # sha-pinned like any input
    statement("The clinical study report states the primary endpoint was met.")
    assert csr.contains("the primary endpoint was met")
```

`DocRef.contains()` extracts with pinned pure-Python readers (pdf/docx/pptx) and matches whitespace/dash/Markdown-robustly, so a quote split across lines or cells still matches. The match is a pure function of the bytes. There is **no OCR**: a scanned/image-only document raises `EmptyExtraction` rather than silently reporting "not found".

## Composing claims

`uses()` lets one claim build on earlier ones: it merges their sha-pinned inputs into this
claim's provenance (transitively) and hands back their `evidence`. The composed claim can read
no source of its own, yet `grounding trace` still walks it all the way down — change an upstream
dataset and the roll-up breaks too. Provenance is a computed DAG, never hand-maintained.

**Roll up independent results.** A program-level conclusion that rests on several per-dataset
claims — defined in different test files, over different data:

```python
from grounding import uses, statement, strength

@strength("moderate")
def test_effect_replicates_across_cohorts():
    """The biomarker drop holds in two independently-run cohorts."""
    b = uses("test_treatment_lowers_biomarker_vs_vehicle")   # cohort B
    c = uses("test_treatment_lowers_biomarker_cohort_c")     # cohort C, a different test file
    statement(f"the effect replicates: {b['pct_drop']:.0f}% (cohort B) "
              f"and {c['pct_drop']:.0f}% (cohort C)")
    assert b["pct_drop"] > 0 and c["pct_drop"] > 0
```

This claim touches no CSV directly, but its recorded inputs now include *both* cohorts' files,
each sha-pinned. Change either cohort's data and this roll-up — not just the two underlying
claims — shows up as drifted.

**Cross-check data against a document.** Compose a numeric claim with a quote check to assert an
external report and your own data agree — the classic transcription-drift catcher:

```python
from grounding import doc, uses, statement, strength, kind

@kind("external")
@strength("strong")
def test_report_headline_matches_our_data():
    """The CSR's stated drop matches what our tidy data produces — no transcription drift."""
    ours = uses("test_treatment_lowers_biomarker_vs_vehicle")["pct_drop"]
    csr = doc("clinical_summary.pdf")
    statement(f"the CSR's reported reduction matches our computed {ours:.0f}% drop")
    assert csr.contains(f"{ours:.0f}% reduction")
```

This grounds the *agreement* itself: the PDF is pinned by `doc()`, the number is pinned
transitively through `uses()`, and the single assert fails if the report and the data ever
diverge. Each claim stays small and independently reviewable; higher-level claims inherit — never
re-derive — their evidence and provenance.

## Tracing

```bash
grounding trace ./out          # re-verify every claim's inputs still match recorded shas
```

One command answers *"is this conclusion still grounded?"* — the question a reviewer otherwise spends an afternoon on. Exit 0 if grounded, 1 if any input changed or went missing.

## What's in the box

| Piece | What it does |
|---|---|
| **Capture context** | records every tracked read (kind, path, sha256) while a claim runs |
| **Tracked loaders** | `data()`/`load()` (CSV→DataFrame, sha-pinned), `doc()` (any document) |
| **`statement()`** | the claim's proposition — ideally computed from the data so it can't drift |
| **Quote verification** | `DocRef.contains()` — offline, deterministic; raises on unreadable sources |
| **pytest plugin** | wraps every test in a capture, emits `grounding_report.json` |
| **Judgment markers** | `@strength`, `@caveats`, `@kind`, `@reviewed` — the reviewer's surface |
| **`uses()`** | transitive claim composition |
| **Bypass guard** | flags a claim that reads data through an untracked path |
| **`grounding trace`** | walks the provenance DAG; tells you if a conclusion is still grounded |

## Design principles

- **Deterministic & offline.** Pure function of bytes. No network, keys, or model — runs in CI and in massively parallel agent fan-out with nothing to configure.
- **Sha-pinned.** The recorded hash is of exactly the bytes parsed.
- **The test is the spec.** A claim is an ordinary pytest test; your runner, fixtures, and CI just work. Git history of `statement`/`@strength`/`@caveats` is a belief-change ledger.
- **Computed, not curated.** Provenance, composition, and (ideally) the statement itself derive from what ran, so they can't drift from reality.
- **Author/critic separation by construction.** Mechanical truth → the assert; honest framing → metadata a fresh-context reviewer judges against the same pinned evidence.

## What it is *not*

- **Not data versioning** (DVC/lakeFS) — it pins shas of files you already have, wherever they live.
- **Not a workflow engine** — it observes reads during a test; it doesn't orchestrate them.
- **Not rendering** — turning grounded claims into a cited report (PDF/HTML) is a separate layer built *on top* of `grounding_report.json`.
- **Not storage/indexing** — the report is the wire format; building a searchable index over it is a consumer's concern.
- **Not an LLM judge** — it runs no model; judgments are recorded by the agents that use it.
