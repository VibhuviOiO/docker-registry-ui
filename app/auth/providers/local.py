"""Break-glass local administrator.

Not a user database: a single account defined entirely by environment variables
that works in every mode. It exists so that a broken IdP, an expired client
secret or an unreachable directory cannot lock every administrator out of the
UI permanently.
"""

import hmac
import logging

from ..models import ROLE_ADMIN, User
from .base import AuthProvider

logger = logging.getLogger(__name__)


class BreakGlassProvider(AuthProvider):
    name = "break-glass"

    def __init__(self, username: str = "", password: str = ""):
        self._username = username or ""
        self._password = password or ""

    def available(self) -> bool:
        return bool(self._username and self._password)

    def authenticate(self, username: str, password: str):
        if not self.available():
            return None

        # Compare both fields in constant time so neither the username nor the
        # password can be probed by timing.
        user_ok = hmac.compare_digest(username or "", self._username)
        pass_ok = hmac.compare_digest(password or "", self._password)

        if user_ok and pass_ok:
            logger.warning("Break-glass administrator %r signed in", self._username)
            return User(
                username=self._username,
                role=ROLE_ADMIN,
                display_name=f"{self._username} (break-glass)",
                provider=self.name,
            )
        return None
