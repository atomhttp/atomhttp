"""
FormData Module
----------------
A browser-``FormData``-flavoured builder for ``multipart/form-data`` and
``application/x-www-form-urlencoded`` request bodies.

Fixes vs. v1 (``atomhttp/core/form_data.py``):
    - Content-type guessing now uses the standard :mod:`mimetypes` module
      instead of a hand-maintained, dozen-entry dict.
    - The boundary is generated with :mod:`secrets` (cryptographically
      random) instead of :mod:`random`, and is regenerated for every call to
      ``to_multipart`` reflecting current field state instead of being
      cached from the first call.
    - File-like objects are read once and cached, so calling
      ``to_multipart()`` twice on the same FormData (e.g. because of a
      retried request) doesn't silently produce an empty body the second
      time around.
"""

import mimetypes
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode


class FormDataItem:
    """A single value appended to a :class:`FormData` field."""

    __slots__ = ("value", "filename", "content_type")

    def __init__(self, value: Any, filename: Optional[str] = None, content_type: Optional[str] = None):
        self.value = value
        self.filename = filename
        self.content_type = content_type

    def resolve_bytes(self) -> bytes:
        """Return this item's value as raw bytes, reading file-likes once."""
        value = self.value
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if isinstance(value, Path):
            return value.read_bytes()
        if hasattr(value, "read"):
            data = value.read()
            self.value = data  # cache so re-reads (e.g. retries) still work
            return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
        return str(value).encode("utf-8")


class FormData:
    """Builder for multipart or URL-encoded form bodies.

    Example:
        >>> form = FormData()
        >>> form.append("username", "john")
        >>> form.append("avatar", open("photo.jpg", "rb"), filename="photo.jpg")
        >>> body, boundary = form.to_multipart()
    """

    def __init__(self) -> None:
        self._data: Dict[str, List[FormDataItem]] = {}

    def append(
        self,
        name: str,
        value: Any,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None:
        """Add a value to ``name``. Existing values for the same name are kept."""
        self._data.setdefault(name, []).append(FormDataItem(value, filename, content_type))

    def set(self, name: str, value: Any, filename: Optional[str] = None, content_type: Optional[str] = None) -> None:
        """Replace all existing values for ``name`` with a single new value."""
        self._data[name] = [FormDataItem(value, filename, content_type)]

    def delete(self, name: str) -> None:
        self._data.pop(name, None)

    def get(self, name: str) -> Optional[Any]:
        items = self._data.get(name)
        return items[0].value if items else None

    def get_all(self, name: str) -> List[Any]:
        return [item.value for item in self._data.get(name, [])]

    def has(self, name: str) -> bool:
        return name in self._data

    def keys(self) -> List[str]:
        return list(self._data.keys())

    def values(self) -> List[Any]:
        return [item.value for items in self._data.values() for item in items]

    def items(self) -> List[Tuple[str, Any]]:
        return [(name, item.value) for name, items in self._data.items() for item in items]

    def is_empty(self) -> bool:
        return not self._data

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    def to_multipart(self) -> Tuple[bytes, str]:
        """Serialize to ``multipart/form-data`` (RFC 7578).

        Returns:
            A ``(body_bytes, boundary)`` tuple.
        """
        boundary = f"----AtomHTTPBoundary{secrets.token_hex(16)}"
        parts: List[bytes] = []

        for name, items in self._data.items():
            for item in items:
                header_lines = [f"--{boundary}"]
                if item.filename:
                    header_lines.append(
                        f'Content-Disposition: form-data; name="{name}"; filename="{item.filename}"'
                    )
                    content_type = item.content_type or self._guess_content_type(item.filename)
                    header_lines.append(f"Content-Type: {content_type}")
                else:
                    header_lines.append(f'Content-Disposition: form-data; name="{name}"')
                    if item.content_type:
                        header_lines.append(f"Content-Type: {item.content_type}")

                header = ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8")
                parts.append(header)
                parts.append(item.resolve_bytes())
                parts.append(b"\r\n")

        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(parts), boundary

    def to_urlencoded(self) -> str:
        """Serialize to ``application/x-www-form-urlencoded``.

        Only the first value of each field is included, matching how HTML
        forms behave without ``multipart/form-data``.
        """
        params = {name: items[0].value for name, items in self._data.items() if items}
        return urlencode(params)
