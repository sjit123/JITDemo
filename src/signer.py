from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from src import InvalidToken


class Signer:
    """Signs and verifies short-lived JWT tokens used by the demo vault."""

    def __init__(self) -> None:
        self._key: bytes = secrets.token_bytes(32)
        self._algorithm: str = "HS256"

    def encode(self, claims: dict[str, Any]) -> str:
        payload = dict(claims)
        now = datetime.now(UTC)
        payload.setdefault("iat", int(now.timestamp()))

        if "exp" not in payload:
            payload["exp"] = int((now + timedelta(seconds=60)).timestamp())

        try:
            return jwt.encode(payload, self._key, algorithm=self._algorithm)
        except jwt.PyJWTError as exc:
            raise InvalidToken("failed to encode token") from exc

    def decode(self, token: str) -> dict[str, Any]:
        try:
            decoded = jwt.decode(token, self._key, algorithms=[self._algorithm])
            return dict(decoded)
        except jwt.ExpiredSignatureError as exc:
            raise InvalidToken("expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidToken("invalid token") from exc
