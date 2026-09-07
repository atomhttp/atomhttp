"""
Progress Module
-----------------
Small helper used by the adapters to report upload/download progress via
the ``on_upload_progress`` / ``on_download_progress`` callbacks.
"""

from typing import Callable, Optional


class ProgressTracker:
    """Tracks bytes transferred and notifies a callback on each update.

    The callback receives ``(loaded, total)``; ``total`` is ``0`` when the
    size is unknown ahead of time (e.g. chunked responses without
    ``Content-Length``).
    """

    def __init__(self, callback: Optional[Callable[[int, int], None]] = None, total: int = 0):
        self.callback = callback
        self.total = total
        self.loaded = 0

    def update(self, loaded: int, total: Optional[int] = None) -> None:
        self.loaded = loaded
        if total is not None:
            self.total = total
        if self.callback:
            # A broken progress callback should never take down the request.
            try:
                self.callback(self.loaded, self.total)
            except Exception:
                pass

    def reset(self) -> None:
        self.loaded = 0
