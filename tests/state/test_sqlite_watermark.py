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
