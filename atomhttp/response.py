"""
Response Module
----------------
:class:`Response` wraps a completed HTTP response with an axios-like,
synchronous-by-default interface. There is nothing async about this object
in v2 -- ``response.data`` is already the fully parsed body by the time you
get it back, whether you called the sync or async client.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Response:
    """A completed HTTP response.

    Attributes:
        data: Parsed response body. Shape depends on the request's
            ``responseType``:
                - ``"json"``: ``dict``/``list``/other JSON-decoded value
                - ``"text"``: ``str``
                - ``"blob"`` / ``"arraybuffer"``: ``bytes``
                - ``"stream"``: a raw, readable ``urllib3.HTTPResponse``.
                  The underlying connection is held open for you to read
                  from -- call ``response.data.release_conn()`` (or
                  ``.close()``) once you're done with it.
        status: HTTP status code, e.g. ``200``.
        status_text: HTTP reason phrase, e.g. ``"OK"``.
        headers: Response headers.
        config: The final :class:`~atomhttp.config.RequestConfig` used.
        request: Alias of ``config``, kept for axios-style familiarity.
        elapsed: Wall-clock seconds the request took, or ``None`` if not
            measured (e.g. mock responses).
        url: The final URL the response was received from, after redirects.
    """

    data: Any
    status: int
    status_text: str
    headers: Dict[str, str] = field(default_factory=dict)
    config: Any = None
    request: Any = None
    elapsed: Optional[float] = None
    url: Optional[str] = None

    def __repr__(self) -> str:
        return f"<Response [{self.status} {self.status_text}]>"

    @property
    def ok(self) -> bool:
        """``True`` for 2xx status codes."""
        return 200 <= self.status < 300

    def raise_for_status(self) -> "Response":
        """Raise :class:`~atomhttp.errors.AtomHTTPRequestError` if not ``ok``.

        Returns ``self`` so calls can be chained, e.g.::

            data = client.get("/users").raise_for_status().data
        """
        if not self.ok:
            from .errors import AtomHTTPRequestError

            raise AtomHTTPRequestError(
                f"Request failed with status code {self.status}",
                request=self.request,
                config=self.config,
                response=self,
            )
        return self
