"""End-to-end: run pytest on a sample claim and inspect the emitted grounding_report.json.

Uses pytest's ``pytester`` in a subprocess so the plugin loads via its entry point.
"""
import json


SAMPLE = '''
from grounding import data, statement, evidence, strength, caveats

@strength("strong")
@caveats("single run")
def test_high_dose_knockdown():
    df = data("measurements.csv")
    hi = df[df.dose == 300].knockdown.mean()
    statement(f"Knockdown reached {hi:.0f}% at the 300 nM dose")
    evidence(knockdown_pct=round(float(hi), 1))
    assert hi > 50
'''

CSV = "dose,knockdown\n300,53.0\n300,53.0\n30,10.0\n"


def test_plugin_emits_grounded_claim(pytester):
    import pytest
    pytest.importorskip("pandas")

    pytester.makepyfile(test_claim=SAMPLE)
    (pytester.path / "measurements.csv").write_text(CSV)

    result = pytester.runpytest_subprocess("--grounding-out", str(pytester.path))
    result.assert_outcomes(passed=1)

    report = json.loads((pytester.path / "grounding_report.json").read_text())
    claims = report["claims"]
    assert len(claims) == 1
    c = claims[0]
    assert c["statement"] == "Knockdown reached 53% at the 300 nM dose"
    assert c["strength"] == "strong"
    assert c["caveats"] == "single run"
    assert c["evidence"] == {"knockdown_pct": 53.0}
    assert c["outcome"] == "passed"
    # provenance captured automatically, sha-pinned
    assert len(c["inputs"]) == 1
    assert c["inputs"][0]["path"].endswith("measurements.csv")
    assert len(c["inputs"][0]["sha256"]) == 64
    assert c["advisories"] == []   # statement present, no untracked reads


def test_plugin_flags_missing_statement(pytester):
    pytester.makepyfile(test_nostmt='''
def test_bare():
    assert 1 + 1 == 2
''')
    result = pytester.runpytest_subprocess("--grounding-out", str(pytester.path))
    result.assert_outcomes(passed=1)
    c = json.loads((pytester.path / "grounding_report.json").read_text())["claims"][0]
    assert c["statement"] is None
    assert any("no statement()" in a for a in c["advisories"])
