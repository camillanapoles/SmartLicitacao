"""Custom exceptions for PNCP client operations."""


class PNCPAPIError(Exception):
    """Base exception for PNCP API communication errors."""

    pass


class PNCPRateLimitError(PNCPAPIError):
    """Raised when API rate limit is exceeded (HTTP 429)."""

    def __init__(self, *args, retry_after: int = 60):
        super().__init__(*args)
        self.retry_after = retry_after


class PNCPTimeoutError(PNCPAPIError):
    """Raised when API request times out."""

    pass


class PNCPServerError(PNCPAPIError):
    """Raised when API returns a server error (5xx)."""

    pass
