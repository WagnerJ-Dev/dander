"""Raw schema declaration contracts for hosted endpoint execution."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dander.ingestion import Endpoint, RawField


def test_endpoint_accepts_recursive_alias_normalized_raw_schema() -> None:
    endpoint = Endpoint.model_validate(
        {
            "name": "companies",
            "path": "/companies",
            "primary_key": ["id"],
            "incremental_cursor": "updated_at",
            "raw_schema": [
                {"name": "id", "type": "integer", "mode": "required"},
                {"name": "updated_at", "type": "timestamp"},
                {
                    "name": "properties",
                    "type": "struct",
                    "fields": [{"name": "active", "type": "boolean"}],
                },
            ],
        }
    )

    assert endpoint.raw_schema[0] == RawField(
        name="id",
        data_type="INT64",
        mode="REQUIRED",
    )
    assert endpoint.raw_schema[2].data_type == "RECORD"
    assert endpoint.raw_schema[2].fields[0].data_type == "BOOL"


@pytest.mark.parametrize(
    ("field", "match"),
    [
        ({"name": "bad-name", "type": "STRING"}, "identifiers"),
        ({"name": "value", "type": "UNSUPPORTED"}, "unsupported raw schema type"),
        ({"name": "value", "type": "STRING", "mode": "MAYBE"}, "unsupported raw schema mode"),
        ({"name": "value", "type": "RECORD"}, "must declare nested fields"),
        (
            {
                "name": "value",
                "type": "STRING",
                "fields": [{"name": "nested", "type": "STRING"}],
            },
            "only RECORD",
        ),
    ],
)
def test_raw_field_rejects_invalid_declaration(
    field: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        RawField.model_validate(field)


def test_endpoint_schema_requires_unique_fields_keys_and_cursor() -> None:
    with pytest.raises(ValidationError, match="raw schema field names must be unique"):
        Endpoint.model_validate(
            {
                "name": "records",
                "path": "/records",
                "raw_schema": [
                    {"name": "id", "type": "STRING"},
                    {"name": "id", "type": "STRING"},
                ],
            }
        )

    with pytest.raises(ValidationError, match="missing primary-key field"):
        Endpoint.model_validate(
            {
                "name": "records",
                "path": "/records",
                "primary_key": ["id"],
                "raw_schema": [{"name": "label", "type": "STRING"}],
            }
        )

    with pytest.raises(ValidationError, match="missing incremental cursor"):
        Endpoint.model_validate(
            {
                "name": "records",
                "path": "/records",
                "incremental_cursor": "updated_at",
                "raw_schema": [{"name": "id", "type": "STRING"}],
            }
        )
