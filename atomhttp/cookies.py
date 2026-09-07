"""
Cookie Jar Module
------------------
In v1, ``atomhttp/utils/cookies.py`` defined a ``CookieManager`` class that
was never imported by the request pipeline -- cookies from ``Set-Cookie``
were simply dropped, and nothing was ever sent back on ``Cookie``. This
module replaces it with a jar that is actually wired into
:class:`~atomhttp.client.AtomHTTP`.

Rather than re-implement RFC 6265 cookie matching (domains, paths,
expiry, secure/http-only flags, ...) by hand, this wraps the battle-tested
:mod:`http.cookiejar` from the standard library. The two small shim classes
below adapt urllib3's request/response shapes to the interface
``http.cookiejar.CookieJar`` expects, which is exactly the technique other
major HTTP libraries use for this.
"""

from http.cookiejar import Cookie, CookieJar as _StdCookieJar
from typing import Dict, Optional
from urllib.parse import urlsplit


class _RequestShim:
    """Adapts an outgoing request to the interface CookieJar expects."""

    def __init__(self, url: str, headers: Dict[str, str]):
        self._url = url
        self._headers = headers
        parts = urlsplit(url)
        self._is_https = parts.scheme == "https"

    def get_full_url(self) -> str:
        return self._url

    def get_host(self) -> str:
        return urlsplit(self._url).netloc.split("@")[-1].split(":")[0]

    # http.cookiejar calls this "origin_req_host" for third-party checks;
    # we don't distinguish first/third-party requests, so it's the same host.
    @property
    def origin_req_host(self) -> str:
        return self.get_host()

    def is_unverifiable(self) -> bool:
        return False

    def has_header(self, name: str) -> bool:
        return name in self._headers

    def get_header(self, name: str, default=None):
        return self._headers.get(name, default)

    def add_unredirected_header(self, name: str, value: str) -> None:
        self._headers[name] = value

    @property
    def type(self) -> str:
        return "https" if self._is_https else "http"

    @property
    def unverifiable(self) -> bool:
        return False


class _ResponseShim:
    """Adapts an incoming response's headers to the interface CookieJar expects."""

    def __init__(self, headers: Dict[str, str], raw_set_cookie_headers):
        self._headers = headers
        self._set_cookie_headers = raw_set_cookie_headers

    def info(self):
        return self

    def get_all(self, name: str, default=None):
        if name.lower() == "set-cookie":
            return self._set_cookie_headers or default
        value = self._headers.get(name)
        return [value] if value is not None else default


class CookieJar:
    """A persistent, per-client cookie jar backed by :mod:`http.cookiejar`.

    Example:
        >>> jar = CookieJar()
        >>> jar.extract("https://api.example.com/login", resp_headers, ["session=abc; Path=/"])
        >>> jar.header_for("https://api.example.com/users")
        'session=abc'
    """

    def __init__(self) -> None:
        self._jar = _StdCookieJar()

    def extract(self, url: str, response_headers: Dict[str, str], set_cookie_headers) -> None:
        """Store any cookies present in a response's ``Set-Cookie`` header(s)."""
        if not set_cookie_headers:
            return
        request = _RequestShim(url, {})
        response = _ResponseShim(response_headers, set_cookie_headers)
        self._jar.extract_cookies(response, request)  # type: ignore[arg-type]

    def header_for(self, url: str) -> Optional[str]:
        """Build the ``Cookie`` header value to send for a request to ``url``."""
        headers: Dict[str, str] = {}
        request = _RequestShim(url, headers)
        self._jar.add_cookie_header(request)  # type: ignore[arg-type]
        return headers.get("Cookie")

    def get(self, name: str, domain: Optional[str] = None) -> Optional[str]:
        """Look up a single cookie's value by name (and optionally domain)."""
        for cookie in self._jar:
            if cookie.name == name and (domain is None or cookie.domain.endswith(domain)):
                return cookie.value
        return None

    def set(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        """Manually inject a cookie into the jar."""
        cookie = Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=bool(domain),
            domain_initial_dot=domain.startswith("."),
            path=path,
            path_specified=True,
            secure=False,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
        )
        self._jar.set_cookie(cookie)

    def clear(self) -> None:
        self._jar.clear()
