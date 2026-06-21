import json

from grounding import sha256
from grounding import trace as T


def _write_report(dirpath, src):
    rec = {
        "claims": [{
            "id": "test_x.py::test_a",
            "statement": "x holds",
            "outcome": "passed",
            "inputs": [{"kind": "data", "path": str(src), "sha256": sha256(src.read_bytes()),
                        "via": "tracked"}],
        }]
    }
    (dirpath / "grounding_report.json").write_text(json.dumps(rec))


def test_trace_grounded_then_broken_on_change(tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("a,b\n1,2\n")
    _write_report(tmp_path, src)

    res = T.trace(tmp_path)
    assert res["status"] == "GROUNDED"
    assert res["claims"][0]["breaks"] == []

    src.write_text("a,b\n1,3\n")           # the evidence moved under the claim
    res2 = T.trace(tmp_path / "grounding_report.json")
    assert res2["status"] == "BROKEN"
    assert any("changed" in b for b in res2["claims"][0]["breaks"])


def test_trace_missing_input(tmp_path):
    src = tmp_path / "gone.csv"
    src.write_text("a\n1\n")
    _write_report(tmp_path, src)
    src.unlink()
    res = T.trace(tmp_path)
    assert res["status"] == "BROKEN"
    assert any("missing" in b for b in res["claims"][0]["breaks"])


def test_trace_no_report(tmp_path):
    assert T.trace(tmp_path)["status"] == "NO_REPORT"
