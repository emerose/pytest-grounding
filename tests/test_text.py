from grounding._normalize import fold_match
from grounding import match_phrase


def test_normalizer_is_public_api():
    # collapse_ws + fold_match are part of the public surface so consumers can share the
    # one canonical fold (e.g. a verdict-cache identity that must agree with quote matching).
    import grounding

    assert {"collapse_ws", "fold_match", "match_phrase", "sha256"} <= set(grounding.__all__)
    assert grounding.fold_match("Ube3a–dosage  *gene*") == "Ube3a-dosage gene"
    assert grounding.collapse_ws("a   b\n c") == "a b c"


def test_fold_match_folds_dashes_markdown_and_whitespace():
    assert fold_match("Ube3a–dosage  *gene*") == "Ube3a-dosage gene"


def test_match_phrase_survives_line_splits_and_endash():
    # A quote the extractor split across lines, with an en-dash where the quote has a hyphen.
    text = "the primary\nendpoint was\nmet at week-12"
    assert match_phrase("the primary endpoint was met at week–12", text)


def test_match_phrase_verbatim_when_normalize_off():
    assert not match_phrase("a  b", "a b", normalize_ws=False)
    assert match_phrase("a b", "x a b y", normalize_ws=False)
