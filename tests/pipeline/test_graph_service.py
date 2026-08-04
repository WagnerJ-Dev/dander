"""Tests for the bounded Druff-to-Dander graph document bridge."""

from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from dander.pipeline import Node, PipelineGraph, dump_graph_to_yaml, load_graph_from_yaml
from dander.pipeline.graph import NodeVisual, Position
from dander.pipeline.graph_service import (
    GRAPH_API_PATH,
    GraphDocumentConflictError,
    GraphDocumentStore,
    GraphDocumentValidationError,
    create_graph_server,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

ORIGIN = "http://localhost:3000"


def _write_graph(path: Path) -> PipelineGraph:
    graph = PipelineGraph(
        name="visual-edit",
        nodes=[
            Node(
                id="source",
                type="source",
                name="Source",
                config={"connector": "greenhouse", "unmodeled": {"kept": True}},
                visual=NodeVisual(position=Position(x=10, y=20), color="#123456", icon="building"),
            )
        ],
    )
    dump_graph_to_yaml(graph, path)
    return graph


def test_store_saves_valid_graph_and_preserves_unedited_model_fields(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    original = _write_graph(path)
    store = GraphDocumentStore(path)
    opened = store.load()
    payload = opened.graph.model_dump(by_alias=True, mode="json")
    payload["nodes"][0]["visual"]["position"] = {"x": 50, "y": 75}

    saved = store.save(payload, expected_revision=opened.revision)

    assert saved.revision != opened.revision
    reloaded = load_graph_from_yaml(path)
    assert reloaded.nodes[0].visual is not None
    assert reloaded.nodes[0].visual.position == Position(x=50, y=75)
    assert reloaded.nodes[0].visual.color == original.nodes[0].visual.color  # type: ignore[union-attr]
    assert reloaded.nodes[0].visual.icon == original.nodes[0].visual.icon  # type: ignore[union-attr]
    assert reloaded.nodes[0].config.model_dump()["unmodeled"] == {"kept": True}  # type: ignore[union-attr]


def test_store_rejects_stale_revision_without_changing_file(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)
    store = GraphDocumentStore(path)
    opened = store.load()
    before = path.read_bytes()

    with pytest.raises(GraphDocumentConflictError, match="changed after Druff opened"):
        store.save(
            opened.graph.model_dump(by_alias=True, mode="json"),
            expected_revision="0" * 64,
        )

    assert path.read_bytes() == before


def test_store_rejects_invalid_graph_without_changing_file(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)
    store = GraphDocumentStore(path)
    opened = store.load()
    before = path.read_bytes()
    invalid = opened.graph.model_dump(by_alias=True, mode="json")
    invalid["edges"] = [{"from": "source", "to": "missing"}]

    with pytest.raises(GraphDocumentValidationError, match="Dangling edge"):
        store.save(invalid, expected_revision=opened.revision)

    assert path.read_bytes() == before


def test_store_rejects_unknown_top_level_field_on_load(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)
    payload = yaml.safe_load(path.read_text())
    payload["newer_dander_field"] = {"must_not": "disappear"}
    path.write_text(yaml.safe_dump(payload, sort_keys=False))

    with pytest.raises(GraphDocumentValidationError, match="PipelineGraph contract"):
        GraphDocumentStore(path).load()


def test_store_rejects_unknown_nested_field_without_changing_file(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)
    store = GraphDocumentStore(path)
    opened = store.load()
    before = path.read_bytes()
    payload = opened.graph.model_dump(by_alias=True, mode="json")
    payload["nodes"][0]["newer_dander_field"] = {"must_not": "disappear"}

    with pytest.raises(GraphDocumentValidationError, match="PipelineGraph contract"):
        store.save(payload, expected_revision=opened.revision)

    assert path.read_bytes() == before


@contextmanager
def _running_server(path: Path) -> Iterator[tuple[str, int]]:
    server = create_graph_server(path, origin=ORIGIN, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = server.server_address
        yield str(address[0]), int(address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(
    address: tuple[str, int],
    method: str,
    *,
    payload: object | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    connection = http.client.HTTPConnection(*address, timeout=5)
    body = None if payload is None else json.dumps(payload)
    request_headers = {"Origin": ORIGIN, **(headers or {})}
    connection.request(method, GRAPH_API_PATH, body=body, headers=request_headers)
    response = connection.getresponse()
    response_body = json.loads(response.read())
    response_headers = {name.lower(): value for name, value in response.getheaders()}
    connection.close()
    return response.status, response_body, response_headers


def test_http_get_and_conditional_put_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)

    with _running_server(path) as address:
        status, graph, headers = _request(address, "GET")
        assert status == 200
        assert headers["access-control-allow-origin"] == ORIGIN
        graph["nodes"][0]["visual"]["position"] = {"x": 125, "y": 250}

        status, saved, saved_headers = _request(
            address,
            "PUT",
            payload=graph,
            headers={"Content-Type": "application/json", "If-Match": headers["etag"]},
        )

    assert status == 200
    assert saved_headers["etag"] != headers["etag"]
    assert saved["nodes"][0]["visual"]["color"] == "#123456"
    reloaded = load_graph_from_yaml(path)
    assert reloaded.nodes[0].visual is not None
    assert reloaded.nodes[0].visual.position == Position(x=125, y=250)


def test_http_rejects_wrong_origin_and_stale_save(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    _write_graph(path)

    with _running_server(path) as address:
        status, graph, headers = _request(address, "GET")
        assert status == 200

        connection = http.client.HTTPConnection(*address, timeout=5)
        connection.request("GET", GRAPH_API_PATH, headers={"Origin": "https://example.com"})
        forbidden = connection.getresponse()
        assert forbidden.status == 403
        forbidden.read()
        connection.close()

        status, error, _ = _request(
            address,
            "PUT",
            payload=graph,
            headers={
                "Content-Type": "application/json",
                "If-Match": '"' + ("0" * 64) + '"',
            },
        )

    assert status == 412
    assert "changed" in error["error"]
    assert headers["etag"] == f'"{GraphDocumentStore(path).load().revision}"'
