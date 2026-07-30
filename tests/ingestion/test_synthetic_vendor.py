"""Live-local proof for the deterministic synthetic vendor connector."""

from __future__ import annotations

from pathlib import Path

from dander.dev.synthetic_vendor import SyntheticVendorServer
from dander.ingestion import DltRestSource, load_source_config
from dander.security import NoAuth

_CONNECTOR = Path(__file__).parents[2] / "connectors" / "synthetic_vendor.yaml"


def _source(server: SyntheticVendorServer) -> DltRestSource:
    config = load_source_config(_CONNECTOR).model_copy(update={"base_url": server.base_url})
    return DltRestSource(config, NoAuth())


def test_cursor_pages_retry_duplicate_keys_and_incremental_updates() -> None:
    with SyntheticVendorServer() as server:
        source = _source(server)

        first = list(source.extract("accounts"))
        first_cursor = max(str(record["updated_at"]) for record in first)
        second = list(source.extract("accounts", since=first_cursor))

        assert [record["id"] for record in first] == [
            "acct-001",
            "acct-002",
            "acct-002",
            "acct-003",
        ]
        assert first[2]["name"] == "Paper Kite Laboratories"
        assert [(record["id"], record["name"]) for record in second] == [
            ("acct-001", "Northwind Observatory Cooperative"),
            ("acct-003", "Juniper Works International"),
        ]
        state = server.snapshot()
        assert state["account_generation"] == 1
        assert state["requests"]["accounts:first"] == 3
        assert state["requests"]["accounts:page-2"] == 2


def test_link_header_pages_retry_and_repeat_a_business_key() -> None:
    with SyntheticVendorServer() as server:
        records = list(_source(server).extract("events"))

        assert [record["id"] for record in records] == [
            "evt-001",
            "evt-002",
            "evt-002",
            "evt-003",
        ]
        state = server.snapshot()
        assert state["requests"] == {"events:1": 2, "events:2": 1}
