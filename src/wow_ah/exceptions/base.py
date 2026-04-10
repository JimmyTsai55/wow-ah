class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class APIError(AppException):
    """Blizzard API related errors."""


class DataError(AppException):
    """Data access / insufficient data errors."""
