"""Deterministic local REST API for end-to-end ingestion exercises.

The server deliberately behaves like a mildly awkward SaaS API: it has cursor and Link-header
pagination, repeats business keys, changes records between traversals, and returns one retryable
error per endpoint. All records and credentials are invented.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from contextlib import AbstractContextManager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

_ACCOUNTS_V1 = (
    (
        {"id": "acct-001", "name": "Northwind Observatory", "updated_at": "2026-01-01T00:00:00Z"},
        {"id": "acct-002", "name": "Paper Kite Labs", "updated_at": "2026-01-01T01:00:00Z"},
    ),
    (
        {
            "id": "acct-002",
            "name": "Paper Kite Laboratories",
            "updated_at": "2026-01-01T02:00:00Z",
        },
        {"id": "acct-003", "name": "Juniper Works", "updated_at": "2026-01-01T03:00:00Z"},
    ),
)
_ACCOUNTS_V2 = (
    (
        {
            "id": "acct-001",
            "name": "Northwind Observatory Cooperative",
            "updated_at": "2026-01-02T00:00:00Z",
        },
    ),
    (
        {
            "id": "acct-003",
            "name": "Juniper Works International",
            "updated_at": "2026-01-02T01:00:00Z",
        },
    ),
)
_EVENTS = (
    (
        {"id": "evt-001", "account_id": "acct-001", "kind": "created"},
        {"id": "evt-002", "account_id": "acct-002", "kind": "opened"},
    ),
    (
        {"id": "evt-002", "account_id": "acct-002", "kind": "opened"},
        {"id": "evt-003", "account_id": "acct-003", "kind": "updated"},
    ),
)


class _State:
    def __init__(self) -> None:
        self.lock = Lock()
        self.requests: Counter[str] = Counter()
        self.account_generation = 0

    def count(self, key: str) -> int:
        with self.lock:
            self.requests[key] += 1
            return self.requests[key]

    def generation(self) -> int:
        with self.lock:
            return self.account_generation

    def finish_account_traversal(self) -> None:
        with self.lock:
            self.account_generation = 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "account_generation": self.account_generation,
                "requests": dict(self.requests),
            }


class _Server(ThreadingHTTPServer):
    state: _State


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json({"status": "ok"})
            return
        if parsed.path == "/v1/accounts":
            self._accounts(parse_qs(parsed.query))
            return
        if parsed.path == "/v1/events":
            self._events(parse_qs(parsed.query))
            return
        self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _accounts(self, query: dict[str, list[str]]) -> None:
        cursor = query.get("cursor", [""])[0]
        if cursor not in {"", "page-2"}:
            self._json({"error": "invalid_cursor"}, status=HTTPStatus.BAD_REQUEST)
            return
        request_key = f"accounts:{cursor or 'first'}"
        if self.server.state.count(request_key) == 1 and not cursor:
            self._json(
                {"error": "synthetic_rate_limit"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
                headers={"Retry-After": "0"},
            )
            return

        page_index = 1 if cursor == "page-2" else 0
        generation = self.server.state.generation()
        pages = _ACCOUNTS_V2 if generation else _ACCOUNTS_V1
        since = query.get("updated_after", [None])[0]
        records = [
            record for record in pages[page_index] if since is None or record["updated_at"] > since
        ]
        next_cursor = "page-2" if page_index == 0 else None
        self._json({"data": records, "meta": {"next_cursor": next_cursor}})
        if page_index == 1:
            self.server.state.finish_account_traversal()

    def _events(self, query: dict[str, list[str]]) -> None:
        try:
            page = int(query.get("page", ["1"])[0])
        except ValueError:
            self._json({"error": "invalid_page"}, status=HTTPStatus.BAD_REQUEST)
            return
        if page not in {1, 2}:
            self._json({"error": "invalid_page"}, status=HTTPStatus.BAD_REQUEST)
            return
        request_key = f"events:{page}"
        if self.server.state.count(request_key) == 1 and page == 1:
            self._json(
                {"error": "synthetic_server_error"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        headers: dict[str, str] = {}
        if page == 1:
            host, port = cast("tuple[str, int]", self.server.server_address)
            next_query = urlencode({"page": 2})
            headers["Link"] = f'<http://{host}:{port}/v1/events?{next_query}>; rel="next"'
        self._json({"data": list(_EVENTS[page - 1])}, headers=headers)

    def _json(
        self,
        payload: object,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


class SyntheticVendorServer(AbstractContextManager["SyntheticVendorServer"]):
    """Own a background synthetic API server for tests and local demonstrations."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._server = _Server((host, port), _Handler)
        self._server.state = _State()
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        """Return the bound API base URL, including an ephemeral port when requested."""
        host, port = cast("tuple[str, int]", self._server.server_address)
        return f"http://{host}:{port}/v1"

    def start(self) -> SyntheticVendorServer:
        """Start serving in a daemon thread."""
        if self._thread is not None:
            return self
        self._thread = Thread(
            target=self._server.serve_forever,
            name="dander-synthetic-vendor",
            daemon=True,
        )
        self._thread.start()
        return self

    def snapshot(self) -> dict[str, Any]:
        """Return request counts and the current deterministic data generation."""
        return self._server.state.snapshot()

    def close(self) -> None:
        """Stop the server and release its socket."""
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self._server.server_close()

    def __enter__(self) -> SyntheticVendorServer:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        del exc_info
        self.close()


def main() -> None:
    """Run the synthetic API until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with SyntheticVendorServer(args.host, args.port) as server:
        print(f"Synthetic vendor API listening at {server.base_url}", flush=True)
        print("Endpoints: /accounts (cursor), /events (Link header), /healthz", flush=True)
        try:
            assert server._thread is not None
            server._thread.join()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
