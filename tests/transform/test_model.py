"""Unit tests for ``dander.transform.model.parse_refs``."""

from __future__ import annotations

from pathlib import Path

import pytest

from dander.transform.model import parse_refs

_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        # Multiple distinct refs, order of first appearance preserved.
        (
            "SELECT * FROM {{ ref('a') }} JOIN {{ ref('b') }} ON {{ ref('c') }}",
            ["a", "b", "c"],
        ),
        # Duplicate refs, de-duplicated with first-occurrence order preserved.
        (
            "SELECT * FROM {{ ref('a') }} JOIN {{ ref('b') }} JOIN {{ ref('a') }}",
            ["a", "b"],
        ),
        # No refs at all.
        ("SELECT 1 AS one", []),
        # Empty string input.
        ("", []),
        # Single-quote and double-quote names.
        ("{{ ref('single') }}", ["single"]),
        ('{{ ref("double") }}', ["double"]),
        # Tight whitespace.
        ('{{ref("x")}}', ["x"]),
        # Loose whitespace, inside braces and around parens/quotes.
        ("{{  ref (  'x'  )  }}", ["x"]),
        # Negative: function-like text that merely ends in "ref" must not match.
        ("SELECT * FROM pref('x')", []),
        # Negative: a differently-named Jinja call must not match.
        ("{{ myref('x') }}", []),
        # Negative: a SQL comment mentioning "ref" without braces must not match.
        ("-- references ref('x') for context\nSELECT 1", []),
        # Negative: an unrelated Jinja expression must not match.
        ("{{ some_var }}", []),
    ],
)
def test_parse_refs(sql: str, expected: list[str]) -> None:
    assert parse_refs(sql) == expected


def test_parse_refs_real_model_file() -> None:
    """Integration-style sanity check against a real model in the repo."""
    sql = (_MODELS_DIR / "staging" / "stg_greenhouse__candidates.sql").read_text()
    assert parse_refs(sql) == ["raw_greenhouse_candidates"]
