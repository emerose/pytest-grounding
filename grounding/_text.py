"""Shared text / identifier helpers (leaf module).

Small, dependency-light helpers: the sha256 hasher, the single phrase matcher
``DocRef.contains`` delegates to, and the identifier-column preservation used by
:func:`grounding.load`. Imports only :mod:`grounding._normalize` (pure stdlib) and,
lazily, pandas inside :func:`preserve_identifier`; nothing here imports back up into the
package, so it is safe to import from anywhere.
"""
from __future__ import annotations

import hashlib
import re as _re

from ._normalize import fold_match


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def match_phrase(phrase: str, text: str, *, normalize_ws: bool = True) -> bool:
    """Substring-check ``phrase`` against ``text`` for verbatim-quote matching. With
    ``normalize_ws`` (default) fold both sides first (NFKC + Unicode-dash fold + Markdown
    emphasis strip + whitespace-collapse) so a correct quote isn't defeated by an en-dash,
    a ligature, stored Markdown, or an extractor that split it across runs/lines/cells.
    Case is preserved."""
    if normalize_ws:
        return fold_match(phrase) in fold_match(text)
    return phrase in text


_INT_LIKE = _re.compile(r"^-?\d+$")


def preserve_identifier(col, str_col):
    """Keep a column as faithful strings when pandas' numeric inference would corrupt
    identifiers. Fires only when every non-blank value is a plain integer string AND
    inference would alter it — a leading zero (``"01"`` -> ``1``) or a column floated by
    blank cells (``"73"`` -> ``73.0``). Real measurement columns (decimals, sign-less
    floats, clean blank-free integers) are left numeric and untouched."""
    import pandas as pd

    if not (pd.api.types.is_integer_dtype(col.dtype) or pd.api.types.is_float_dtype(col.dtype)):
        return col  # already object/string
    nonblank = str_col[str_col != ""]
    if not len(nonblank) or not nonblank.map(lambda v: bool(_INT_LIKE.match(v))).all():
        return col  # has decimals / non-integer text -> a real measurement column
    has_leading_zero = nonblank.map(lambda v: len(v) > 1 and v.lstrip("-").startswith("0")).any()
    has_blanks = (str_col == "").any()
    if has_leading_zero or has_blanks:
        return str_col  # identifier-like; keep the exact text
    return col          # clean blank-free integers (counts, indices) stay numeric
