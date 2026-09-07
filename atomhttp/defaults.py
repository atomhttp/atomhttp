"""
Defaults Module
----------------
Holds the base :class:`~atomhttp.config.RequestConfig` that every request
made by a client instance starts from.
"""

from typing import Any, Dict

from .config import RequestConfig
from .version import __version__


class Defaults:
    """Mutable container for a client's default request configuration.

    Example:
        >>> defaults = Defaults()
        >>> defaults.timeout
        30
        >>> defaults.update(RequestConfig(headers={'X-Custom': 'value'}))
        >>> defaults.headers['X-Custom']
        'value'
    """

    def __init__(self) -> None:
        self._config = RequestConfig(
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": f"atomhttp/{__version__}",
            },
            timeout=30,
            maxRedirects=5,
            responseType="json",
            xsrfCookieName="XSRF-TOKEN",
            xsrfHeaderName="X-XSRF-TOKEN",
            withCredentials=False,
            keepAlive=True,
            decompress=True,
            baseURL="",
        )

    def update(self, config: RequestConfig) -> None:
        """Merge non-``None`` values from ``config`` into these defaults.

        Headers are merged key-by-key rather than replaced wholesale, so
        setting one default header doesn't wipe out the others.
        """
        for key, value in config.to_dict().items():
            if not hasattr(self._config, key):
                continue
            if key == "headers" and isinstance(value, dict):
                self._config.headers.update(value)
            else:
                setattr(self._config, key, value)

    def to_dict(self) -> Dict[str, Any]:
        return self._config.to_dict()

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not found normally (i.e. not _config),
        # so this can never recurse.
        return getattr(self._config, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_config":
            super().__setattr__(name, value)
        else:
            setattr(self._config, name, value)
