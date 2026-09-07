"""
A tiny, dependency-free local HTTP server used by the test-suite so tests
don't depend on any external service being reachable.
"""

import gzip
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence default stderr logging
        pass

    # -- helpers --------------------------------------------------------

    def _send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return self._read_chunked_body()
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _read_chunked_body(self):
        chunks = bytearray()
        while True:
            size_line = self.rfile.readline().strip()
            if not size_line:
                break
            size = int(size_line.split(b";")[0], 16)
            if size == 0:
                self.rfile.readline()  # trailing CRLF after the terminating 0-chunk
                break
            chunks.extend(self.rfile.read(size))
            self.rfile.read(2)  # CRLF after each chunk's data
        return bytes(chunks)

    def _echo_payload(self):
        body = self._read_body()
        parsed = urlsplit(self.path)
        data = None
        content_type = self.headers.get("Content-Type", "")
        if body:
            if "application/json" in content_type:
                try:
                    data = json.loads(body.decode("utf-8"))
                except Exception:
                    data = body.decode("utf-8", "replace")
            elif "multipart/form-data" in content_type or "x-www-form-urlencoded" in content_type:
                data = body.decode("utf-8", "replace")
            else:
                data = body.decode("utf-8", "replace")
        return {
            "method": self.command,
            "path": parsed.path,
            "query": {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()},
            "headers": dict(self.headers.items()),
            "data": data,
            "body_length": len(body),
        }

    # -- routing ----------------------------------------------------------

    def _dispatch(self):
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/get" and self.command == "GET":
            self._send_json(200, self._echo_payload())
            return

        if path == "/anything" or path.startswith("/anything/"):
            self._send_json(200, self._echo_payload())
            return

        if path.startswith("/status/"):
            code = int(path.rsplit("/", 1)[-1])
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/redirect/"):
            n = int(path.rsplit("/", 1)[-1])
            if n <= 0:
                self._send_json(200, {"redirected": True})
                return
            self.send_response(302)
            self.send_header("Location", f"/redirect/{n - 1}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/delay/"):
            seconds = float(path.rsplit("/", 1)[-1])
            time.sleep(seconds)
            self._send_json(200, {"delayed": seconds})
            return

        if path == "/cookies/set":
            qs = parse_qs(parsed.query)
            self.send_response(200)
            for k, values in qs.items():
                self.send_header("Set-Cookie", f"{k}={values[0]}; Path=/")
            body = b"{}"
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/cookies":
            self._send_json(200, {"cookie": self.headers.get("Cookie")})
            return

        if path == "/gzip":
            payload = json.dumps({"gzipped": True}).encode("utf-8")
            compressed = gzip.compress(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
            return

        if path == "/large":
            size = int(parse_qs(parsed.query).get("size", ["1000000"])[0])
            body = b"x" * size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/basic-auth/"):
            _, _, user, pwd = path.split("/", 3)
            import base64

            auth = self.headers.get("Authorization", "")
            ok = False
            if auth.startswith("Basic "):
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                ok = decoded == f"{user}:{pwd}"
            self._send_json(200 if ok else 401, {"authenticated": ok})
            return

        if path == "/headers":
            self._send_json(200, {"headers": dict(self.headers.items())})
            return

        self._send_json(404, {"error": "not found", "path": path})

    def do_GET(self):
        self._read_body()
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


class TestServer:
    """A local HTTP server bound to an ephemeral port on 127.0.0.1."""

    def __init__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "TestServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
