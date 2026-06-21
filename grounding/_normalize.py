"""The one verbatim-quote text normalizer (pure stdlib).

A single place for the text normalization that quote matching depends on. Keeping it
in one function means a verbatim quote folds to exactly one canonical form everywhere
it is compared — so a correct quote is never defeated by a glyph variant, and any future
identity/caching layer built on top stays consistent with the matcher by construction.
"""
from __future__ import annotations

import unicodedata

# Unicode dash/hyphen variants that publishers and PDF extractors use interchangeably
# with ASCII "-": en/em dashes, the Unicode hyphen, non-breaking hyphen, minus sign, etc.
# Folding them (plus NFKC, which normalizes ligatures/full-width/compatibility forms) lets
# a verbatim quote match stored text without the author reproducing the exact glyph — the
# single most common reason a real, correct quote fails a naive substring check.
_DASHES = "‐‑‒–—―⁃−﹘﹣－"
_DASH_MAP = {ord(c): "-" for c in _DASHES}


def collapse_ws(s: str) -> str:
    """Collapse every run of whitespace to a single space (and strip). Quote matching is
    *verbatim*, but extractors split a sentence across runs/lines/cells (worst in slide
    decks); normalizing both sides makes a short quote match reliably."""
    return " ".join(s.split())


def fold_match(s: str) -> str:
    """Normalize text for verbatim-quote matching: NFKC-normalize, fold Unicode dashes to
    ASCII ``-``, drop Markdown emphasis markers (``*``/``_``), then collapse whitespace.
    Case is preserved (the quote stays verbatim)."""
    folded = (
        unicodedata.normalize("NFKC", s)
        .translate(_DASH_MAP)
        .replace("*", "")
        .replace("_", "")
    )
    return collapse_ws(folded)
