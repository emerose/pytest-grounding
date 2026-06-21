import pytest

from grounding import loaders
from grounding.loaders import DocRef, EmptyExtraction, UnsupportedDocFormat


def test_docref_contains_uses_folded_match(tmp_path, monkeypatch):
    f = tmp_path / "report.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setitem(loaders._TEXT_READERS, ".pdf",
                        lambda p: "the primary\nendpoint was met")
    ref = DocRef(f, "deadbeef")
    assert ref.contains("the primary endpoint was met")
    assert not ref.contains("the secondary endpoint was met")


def test_docref_empty_extraction_raises(tmp_path, monkeypatch):
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 image only")
    monkeypatch.setitem(loaders._TEXT_READERS, ".pdf", lambda p: "   \n  ")
    with pytest.raises(EmptyExtraction):
        DocRef(f, "deadbeef").text()


def test_docref_unsupported_format(tmp_path):
    f = tmp_path / "notes.rtf"
    f.write_text("hi")
    with pytest.raises(UnsupportedDocFormat):
        DocRef(f, "deadbeef").text()


def test_load_csv_sets_attrs_and_preserves_identifiers(tmp_path):
    pytest.importorskip("pandas")
    csv = tmp_path / "m.csv"
    csv.write_text("guide_id,knockdown\n01,53.2\n08,47.0\n")
    df = loaders.load(csv)
    assert df.attrs["source"] == str(csv)
    assert len(df.attrs["sha256"]) == 64
    # leading-zero identifier kept as faithful string, not coerced to int
    assert list(df["guide_id"]) == ["01", "08"]
    assert df["knockdown"].tolist() == [53.2, 47.0]
