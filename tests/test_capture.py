import grounding
from grounding._capture import Capture, _CURRENT


def _in_capture(cap, fn):
    token = _CURRENT.set(cap)
    try:
        return fn()
    finally:
        _CURRENT.reset(token)


def test_record_dedups_same_kind_and_path():
    cap = Capture(claim_id="t")
    cap.record("data", "a.csv", "sha1")
    cap.record("data", "a.csv", "sha1")
    cap.record("doc", "a.csv", "sha1")  # different kind -> distinct
    assert len(cap.inputs) == 2


def test_statement_and_evidence_write_the_active_capture():
    cap = Capture(claim_id="t")
    _in_capture(cap, lambda: grounding.statement("the thing holds"))
    _in_capture(cap, lambda: grounding.evidence(x=1, y=2))
    assert cap.statement == "the thing holds"
    assert cap.evidence == {"x": 1, "y": 2}


def test_uses_merges_prior_inputs_and_returns_evidence():
    grounding.registry.clear()
    grounding.registry["test_f.py::test_a"] = {
        "id": "test_f.py::test_a",
        "inputs": [{"kind": "data", "path": "a.csv", "sha256": "sha1", "via": "tracked"}],
        "evidence": {"k": 9},
    }
    cap = Capture(claim_id="test_f.py::test_b")
    ev = _in_capture(cap, lambda: grounding.uses("test_a"))   # bare name resolves
    assert ev == {"k": 9}
    assert cap.inputs[0]["path"] == "a.csv" and cap.inputs[0]["via"] == "uses"
