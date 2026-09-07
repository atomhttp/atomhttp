"""
urllib3 Transport Adapter
---------------------------
This is the real, production HTTP transport for AtomHTTP. It replaces the
v1 adapter (which used ``aiohttp`` and, confusingly, existed in two
separate, mostly-duplicate implementations -- ``core/adapters.py`` which
was actually wired up, and ``adapters/http_adapter.py`` which was dead
code that was never imported by anything).

Everything here is synchronous/blocking by design -- see
:mod:`atomhttp.adapters.base` for why. urllib3 already gives us:
    - Connection pooling & keep-alive (``PoolManager``)
    - Thread-safety (pools are safe to share across threads, which is
      exactly what the async client needs when it runs requests in a
      thread pool)
    - Retries with backoff and redirect handling (``urllib3.util.Retry``)
    - Proxy support (``ProxyManager``)
    - Streaming reads for real download progress and bounded memory use
"""

import base64
import json
import socket
import ssl
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

import urllib3
from urllib3.connection import HTTPConnection
from urllib3.connectionpool import HTTPConnectionPool
from urllib3.util.retry import Retry
from urllib3.util.timeout import Timeout

from ..config import RequestConfig
from ..cookies import CookieJar
from ..errors import (
    AtomHTTPError,
    AtomHTTPNetworkError,
    AtomHTTPRequestError,
    AtomHTTPTimeoutError,
)
from ..form_data import FormData
from ..progress import ProgressTracker
from ..response import Response
from .base import BaseAdapter

_CHUNK_SIZE = 65536


# --------------------------------------------------------------------------
# Optional Unix domain socket support (e.g. talking to /var/run/docker.sock).
# urllib3 has no built-in support for this, so we provide a minimal
# connection/pool pair that dials AF_UNIX instead of AF_INET.
# --------------------------------------------------------------------------
class _UnixSocketConnection(HTTPConnection):
    def __init__(self, socket_path: str, timeout=None, **kwargs):
        self._socket_path = socket_path
        super().__init__("localhost", timeout=timeout, **kwargs)

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.timeout is not None and self.timeout is not socket.getdefaulttimeout():
            sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


class _UnixSocketConnectionPool(HTTPConnectionPool):
    def __init__(self, socket_path: str, **kwargs):
        self._socket_path = socket_path
        super().__init__("localhost", **kwargs)

    def _new_conn(self):
        return _UnixSocketConnection(self._socket_path, timeout=self.timeout.connect_timeout)


class HTTPAdapter(BaseAdapter):
    """Production adapter backed entirely by :mod:`urllib3`.

    A single adapter instance keeps a small cache of pool managers so
    connection pooling/keep-alive is preserved across requests, even as
    per-request settings (TLS verification, proxy) vary.
    """

    def __init__(self, pool_maxsize: int = 20, num_pools: int = 20):
        self.pool_maxsize = pool_maxsize
        self.num_pools = num_pools
        self._pools: Dict[Tuple, Any] = {}

    # -- pool management ---------------------------------------------------

    def _pool_key(self, config: RequestConfig) -> Tuple:
        proxy_host = config.proxy.get("host") if config.proxy else None
        return (bool(config.verify), proxy_host, config.socketPath)

    def _get_pool(self, config: RequestConfig):
        key = self._pool_key(config)
        pool = self._pools.get(key)
        if pool is not None:
            return pool

        if config.socketPath:
            pool = _UnixSocketConnectionPool(
                config.socketPath,
                maxsize=self.pool_maxsize,
                timeout=Timeout(total=60),
            )
            self._pools[key] = pool
            return pool

        common_kwargs: Dict[str, Any] = dict(
            maxsize=self.pool_maxsize,
            num_pools=self.num_pools,
            retries=False,  # we build a fresh Retry object per-request
            block=False,
        )
        if not config.verify:
            common_kwargs["cert_reqs"] = "CERT_NONE"
            common_kwargs["assert_hostname"] = False
        else:
            common_kwargs["cert_reqs"] = "CERT_REQUIRED"

        if config.proxy and config.proxy.get("host"):
            proxy_headers = {}
            auth = config.proxy.get("auth") or {}
            if auth.get("username") and auth.get("password"):
                creds = f"{auth['username']}:{auth['password']}"
                encoded = base64.b64encode(creds.encode()).decode()
                proxy_headers["Proxy-Authorization"] = f"Basic {encoded}"
            pool = urllib3.ProxyManager(
                config.proxy["host"], proxy_headers=proxy_headers, **common_kwargs
            )
        else:
            pool = urllib3.PoolManager(**common_kwargs)

        self._pools[key] = pool
        return pool

    def close(self) -> None:
        for pool in self._pools.values():
            try:
                pool.clear()
            except Exception:
                pass
        self._pools.clear()

    # -- request body preparation -------------------------------------------

    def _prepare_body(self, config: RequestConfig) -> Tuple[Optional[bytes], Optional[str]]:
        """Returns ``(body_bytes, content_type)``. Neither may be set yet."""
        data = config.data
        if data is None:
            return None, None

        if isinstance(data, FormData):
            body, boundary = data.to_multipart()
            return body, f"multipart/form-data; boundary={boundary}"

        if isinstance(data, (dict, list)):
            return json.dumps(data).encode("utf-8"), "application/json"

        if isinstance(data, str):
            return data.encode("utf-8"), "text/plain; charset=utf-8"

        if isinstance(data, (bytes, bytearray)):
            return bytes(data), None

        return str(data).encode("utf-8"), "text/plain; charset=utf-8"

    def _iter_chunks_with_progress(self, body: bytes, tracker: ProgressTracker):
        loaded = 0
        if not body:
            tracker.update(0, 0)
            return
        for i in range(0, len(body), _CHUNK_SIZE):
            chunk = body[i : i + _CHUNK_SIZE]
            loaded += len(chunk)
            tracker.update(loaded, len(body))
            yield chunk

    # -- the main entry point ------------------------------------------------

    def send(self, config: RequestConfig, cookie_jar: Optional[CookieJar] = None) -> Response:
        start = time.perf_counter()
        try:
            return self._send(config, cookie_jar, start)
        except AtomHTTPError:
            raise
        except urllib3.exceptions.MaxRetryError as e:
            reason = e.reason
            # NOTE: urllib3's own exception hierarchy has NewConnectionError
            # (DNS failure, connection refused, ...) *subclass*
            # ConnectTimeoutError, even though those are not timeouts. The
            # more specific NewConnectionError check must run first or every
            # DNS/refused-connection failure gets misreported as a timeout.
            if isinstance(reason, urllib3.exceptions.NewConnectionError):
                raise AtomHTTPNetworkError(f"Connection failed: {reason}", config=config) from e
            if isinstance(reason, (urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.ReadTimeoutError)):
                raise AtomHTTPTimeoutError(f"Request timeout: {reason}", config=config) from e
            raise AtomHTTPNetworkError(f"Connection failed after retries: {reason}", config=config) from e
        except urllib3.exceptions.NewConnectionError as e:
            raise AtomHTTPNetworkError(f"Connection failed: {e}", config=config) from e
        except (urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.ReadTimeoutError, TimeoutError) as e:
            raise AtomHTTPTimeoutError(f"Request timeout after {config.timeout}s: {e}", config=config) from e
        except (
            urllib3.exceptions.ProtocolError,
            urllib3.exceptions.ConnectionError,
            ConnectionError,
            socket.error,
            ssl.SSLError,
        ) as e:
            raise AtomHTTPNetworkError(f"Network error: {e}", config=config) from e
        except urllib3.exceptions.HTTPError as e:
            raise AtomHTTPNetworkError(f"HTTP transport error: {e}", config=config) from e
        except Exception as e:
            raise AtomHTTPRequestError(str(e), request=config, config=config) from e

    def _send(self, config: RequestConfig, cookie_jar: Optional[CookieJar], start: float) -> Response:
        body, content_type = self._prepare_body(config)

        if config.maxBodyLength is not None and config.maxBodyLength >= 0 and body:
            if len(body) > config.maxBodyLength:
                raise AtomHTTPRequestError(
                    f"Request body length {len(body)} exceeds maxBodyLength {config.maxBodyLength}",
                    request=config,
                    config=config,
                )

        headers: Dict[str, str] = dict(config.headers or {})
        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type

        if config.auth and "Authorization" not in headers:
            creds = f"{config.auth.get('username', '')}:{config.auth.get('password', '')}"
            headers["Authorization"] = "Basic " + base64.b64encode(creds.encode()).decode()

        if cookie_jar is not None:
            cookie_header = cookie_jar.header_for(config.url)
            if cookie_header and "Cookie" not in headers:
                headers["Cookie"] = cookie_header
            if config.xsrfCookieName:
                host = urlsplit(config.url).netloc.split(":")[0]
                xsrf_value = cookie_jar.get(config.xsrfCookieName, domain=host)
                if xsrf_value and config.xsrfHeaderName not in headers:
                    headers[config.xsrfHeaderName] = xsrf_value

        chunked = False
        request_body: Any = body
        if body and config.onUploadProgress:
            tracker = ProgressTracker(config.onUploadProgress, len(body))
            request_body = self._iter_chunks_with_progress(body, tracker)
            chunked = True
        elif config.onUploadProgress:
            # No body, but caller still wants a progress callback: fire once.
            config.onUploadProgress(0, 0)

        timeout = Timeout(total=float(config.timeout) if config.timeout else 30.0)

        if config.retryConfig:
            retries = Retry(
                total=None,
                connect=config.retryConfig.get("max_retries", 3),
                read=config.retryConfig.get("max_retries", 3),
                status=config.retryConfig.get("max_retries", 3),
                redirect=config.maxRedirects,
                backoff_factor=config.retryConfig.get("backoff_factor", 0.3),
                status_forcelist=config.retryConfig.get(
                    "status_forcelist", [408, 429, 500, 502, 503, 504]
                ),
                allowed_methods=None,
                raise_on_status=False,
                raise_on_redirect=False,
            )
        else:
            retries = Retry(
                total=None,
                connect=0,
                read=0,
                status=0,
                redirect=config.maxRedirects,
                raise_on_redirect=False,
                raise_on_status=False,
            )

        pool = self._get_pool(config)
        target = urlsplit(config.url)
        request_target = config.url if not config.socketPath else (target.path or "/") + (
            f"?{target.query}" if target.query else ""
        )

        response = pool.request(
            method=config.method.upper(),
            url=request_target,
            body=request_body,
            headers=headers,
            timeout=timeout,
            retries=retries,
            redirect=config.maxRedirects > 0,
            preload_content=False,
            decode_content=config.decompress,
            chunked=chunked,
        )

        try:
            result = self._build_response(config, response, cookie_jar, start)
        except Exception:
            # The response was abandoned mid-read (e.g. maxContentLength was
            # exceeded) or something else went wrong while parsing it. The
            # connection is in an unknown protocol state at this point, so
            # it must be closed and discarded -- NOT returned to the pool.
            # (v1's adapter didn't have pooling at all so this couldn't bite;
            # doing `.close()` on the response but still `.release_conn()`-ing
            # it afterwards, which is an easy mistake once pooling is added,
            # silently corrupts later requests that get handed the dead
            # connection -- this cost real debugging time to track down.)
            response.close()
            raise
        else:
            if config.responseType != "stream":
                # For "stream" responses `result.data` *is* the still-open
                # `response` object, handed to the caller to read at their
                # own pace -- releasing the connection back to the pool now
                # would let another request grab it while this one's body is
                # still being streamed. The caller is responsible for
                # calling `.release_conn()` (or `.close()`) once they're
                # done reading.
                response.release_conn()
            return result

    # -- response handling ---------------------------------------------------

    def _build_response(self, config: RequestConfig, response, cookie_jar: Optional[CookieJar], start: float) -> Response:
        headers = {k: v for k, v in response.headers.items()}

        if cookie_jar is not None:
            set_cookie_headers = response.headers.getlist("Set-Cookie")
            if set_cookie_headers:
                cookie_jar.extract(config.url, headers, set_cookie_headers)

        content_length_header = headers.get("Content-Length")
        if config.maxContentLength is not None and config.maxContentLength >= 0 and content_length_header:
            try:
                declared_length = int(content_length_header)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > config.maxContentLength:
                raise AtomHTTPRequestError(
                    f"Response content length {declared_length} exceeds "
                    f"maxContentLength {config.maxContentLength}",
                    request=config,
                    config=config,
                )

        response_type = config.responseType or "json"

        if response_type == "stream":
            data: Any = response
        else:
            data = self._read_body(config, response, content_length_header)
            data = self._decode_body(data, response_type, headers)

        result = Response(
            data=data,
            status=response.status,
            status_text=response.reason or "",
            headers=headers,
            config=config,
            request=config,
            elapsed=time.perf_counter() - start,
            url=response.geturl() or config.url,
        )

        if config.transformResponse:
            result.data = config.transformResponse(result.data)

        if config.validateStatus and not config.validateStatus(result.status):
            raise AtomHTTPRequestError(
                f"Request failed with status code {result.status}",
                request=config,
                config=config,
                response=result,
            )

        return result

    def _read_body(self, config: RequestConfig, response, content_length_header: Optional[str]) -> bytes:
        tracker = None
        if config.onDownloadProgress:
            expected_total = 0
            if content_length_header:
                try:
                    expected_total = int(content_length_header)
                except ValueError:
                    expected_total = 0
            tracker = ProgressTracker(config.onDownloadProgress, expected_total)

        chunks = bytearray()
        cap = config.maxContentLength if (config.maxContentLength is not None and config.maxContentLength >= 0) else None

        for chunk in response.stream(_CHUNK_SIZE, decode_content=config.decompress):
            chunks.extend(chunk)
            if cap is not None and len(chunks) > cap:
                raise AtomHTTPRequestError(
                    f"Response content length exceeded maxContentLength {cap}",
                    request=config,
                    config=config,
                )
            if tracker:
                tracker.update(len(chunks))

        if tracker and tracker.total == 0:
            tracker.update(len(chunks), len(chunks))

        return bytes(chunks)

    def _decode_body(self, raw: bytes, response_type: str, headers: Dict[str, str]) -> Any:
        if response_type in ("blob", "arraybuffer"):
            return raw

        charset = "utf-8"
        content_type = headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"

        if response_type == "text":
            return raw.decode(charset, errors="replace")

        # default: "json"
        text = raw.decode(charset, errors="replace")
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Server said it would send JSON (or we assumed it) but didn't --
            # hand back the raw text instead of blowing up, same leniency
            # axios/requests offer.
            return text
