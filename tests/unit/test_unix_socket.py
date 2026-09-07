import json
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler

import pytest

from atomhttp import AtomHTTP


class _UnixHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"ok": True, "path": self.path}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def unix_socket_path(tmp_path):
    sock_path = str(tmp_path / "atomhttp-test.sock")
    server = socketserver.UnixStreamServer(sock_path, _UnixHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield sock_path
    server.shutdown()
    server.server_close()
    if os.path.exists(sock_path):
        os.remove(sock_path)


class TestUnixSocket:
    def test_request_over_unix_socket(self, unix_socket_path):
        client = AtomHTTP(timeout=5)
        response = client.get("http://localhost/ping", socketPath=unix_socket_path)
        assert response.status == 200
        assert response.data["ok"] is True

    def test_unix_socket_preserves_path_and_query(self, unix_socket_path):
        client = AtomHTTP(timeout=5)
        response = client.get(
            "http://localhost/items", params={"page": 2}, socketPath=unix_socket_path
        )
        assert "/items" in response.data["path"]
        assert "page=2" in response.data["path"]
