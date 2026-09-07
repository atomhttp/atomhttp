"""
Auth Helpers Module
---------------------
``BasicAuth`` and ``BearerAuth`` are small convenience helpers for building
``Authorization`` headers by hand, e.g. to pass into an interceptor.

Note: for plain HTTP Basic Auth, prefer ``RequestConfig(auth={...})`` --
the client applies it automatically. These classes are for cases like
custom interceptors or non-standard auth flows.
"""

from typing import Dict


class BasicAuth:
    """HTTP Basic Authentication (RFC 7617) header builder."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def get_header(self) -> Dict[str, str]:
        import base64

        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}


class BearerAuth:
    """Bearer token authentication (RFC 6750) header builder."""

    def __init__(self, token: str):
        self.token = token

    def get_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}
