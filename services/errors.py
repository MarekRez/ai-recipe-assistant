"""Shared error type for service-layer failures."""

from __future__ import annotations


class ServiceError(Exception):
    """Failure that should be shown to the user as a short message.

    `user_message` is safe to display in the UI; `detail` is for logs only.
    """

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
