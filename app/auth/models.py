"""Authentication data types."""

from dataclasses import dataclass, field

ROLE_VIEWER = "viewer"
ROLE_ADMIN = "admin"

# Higher rank wins. Anything unrecognised falls back to viewer so a bad group
# name or claim can never silently grant more access.
_RANK = {ROLE_VIEWER: 1, ROLE_ADMIN: 2}


def normalise_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in _RANK else ROLE_VIEWER


@dataclass
class User:
    """An authenticated principal. Never holds a password."""

    username: str
    role: str = ROLE_VIEWER
    display_name: str = ""
    email: str = ""
    provider: str = "local"
    groups: list = field(default_factory=list)

    def __post_init__(self):
        self.role = normalise_role(self.role)
        if not self.display_name:
            self.display_name = self.username

    @property
    def is_admin(self) -> bool:
        return _RANK.get(self.role, 0) >= _RANK[ROLE_ADMIN]

    def to_dict(self) -> dict:
        """Public representation for ``/auth/me``.

        ``groups`` is intentionally omitted: it is only known at login time, and
        the session cookie does not carry it (an AD user can be in hundreds of
        groups, which would not fit in a 4 KB cookie). Including it here would
        always report an empty list and mislead callers.
        """
        return {
            "username": self.username,
            "role": self.role,
            "displayName": self.display_name,
            "email": self.email,
            "provider": self.provider,
            "isAdmin": self.is_admin,
        }

    def to_session(self) -> dict:
        """The minimal payload stored in the session cookie."""
        return {
            "u": self.username,
            "r": self.role,
            "d": self.display_name,
            "e": self.email,
            "p": self.provider,
        }

    @classmethod
    def from_session(cls, data: dict) -> "User":
        return cls(
            username=data.get("u", ""),
            role=data.get("r", ROLE_VIEWER),
            display_name=data.get("d", ""),
            email=data.get("e", ""),
            provider=data.get("p", "session"),
        )


class AuthError(Exception):
    """Authentication failure with a message safe to show a user."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
