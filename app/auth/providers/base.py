"""Provider contract.

A provider returns a :class:`~app.auth.models.User` on success, ``None`` when
the credentials simply do not match it, and raises
:class:`~app.auth.models.AuthError` when the backend itself is unusable
(unreachable directory, TLS failure, ...). That distinction lets the UI say
"directory unavailable" instead of falsely blaming the user's password.
"""


class AuthProvider:
    name = "base"

    def available(self) -> bool:
        """Whether this provider is configured well enough to attempt a login."""
        return True

    def authenticate(self, username: str, password: str):
        """Return a ``User``, ``None``, or raise ``AuthError``."""
        raise NotImplementedError

    # Kept for the UI/tests: never includes secrets.
    def describe(self) -> dict:
        return {"name": self.name, "available": self.available()}
