"""Local SQLite watermark tests for DANDER-21."""

from pathlib import Path

from dander.state import SqliteWatermarkStore


def test_sqlite_watermark_persists_and_updates(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.db"
    store = SqliteWatermarkStore(path)

    assert store.get("greenhouse", "jobs") is None

    store.set("greenhouse", "jobs", "first")
    store.set("greenhouse", "jobs", "second")

    assert SqliteWatermarkStore(path).get("greenhouse", "jobs") == "second"


def test_sqlite_watermark_compare_and_set_rejects_stale_boundary(tmp_path: Path) -> None:
    store = SqliteWatermarkStore(tmp_path / "state.db")

    assert store.compare_and_set(
        "hubspot",
        "companies",
        expected=None,
        cursor="first",
    )
    assert not store.compare_and_set(
        "hubspot",
        "companies",
        expected=None,
        cursor="stale",
    )
    assert store.compare_and_set(
        "hubspot",
        "companies",
        expected="first",
        cursor="second",
    )
    assert store.get("hubspot", "companies") == "second"
