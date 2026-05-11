"""Core package for the JIT access demo."""


class AccessDenied(Exception):
    """Raised when an operation is denied by policy, scope, or lease state."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidToken(Exception):
    """Raised when a token is invalid, malformed, expired, or untrusted."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class PolicyNotFound(Exception):
    """Raised when a requested policy does not exist in the vault."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
