"""LDAP / Active Directory authentication.

Design notes that matter for security and for matching how real directories
behave:

* **Username/password bind.** The configured service account searches for the
  user, then a *new* connection re-binds as that user's DN to verify the
  password. Password hashes are never fetched or compared.
* **Empty passwords are rejected before any bind.** An LDAP simple bind with an
  empty password is a successful *unauthenticated* bind on most servers, so
  forwarding it would turn a blank form submission into a valid login.
* **The username is escaped** before being interpolated into the search filter,
  otherwise it is an LDAP-injection vector.
* **Unreachable != wrong password.** Connection/TLS failures raise ``AuthError``
  with a 503 so the operator sees "directory unavailable" rather than chasing a
  password problem.
* ``ldap3`` is pure Python, so it installs cleanly on the Alpine image. The
  import is guarded because auth is optional: an image or process running with
  ``AUTH_ENABLED=false`` must not require the dependency.
"""

import logging
import ssl

from ..models import ROLE_ADMIN, ROLE_VIEWER, AuthError, User
from .base import AuthProvider

# Group/claim matching lives in one shared module so the LDAP and OIDC providers
# cannot drift apart. split_group_list is re-exported because LDAP-specific
# callers and tests already use that name.
from .groups import matches_group, split_group_list  # noqa: F401

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised by the LDAP integration tests
    from ldap3 import NONE, SUBTREE, Connection, Server, Tls
    from ldap3.core.exceptions import (
        LDAPBindError,
        LDAPException,
        LDAPInvalidCredentialsResult,
    )
    from ldap3.utils.conv import escape_filter_chars

    LDAP3_AVAILABLE = True
except ImportError:  # pragma: no cover
    LDAP3_AVAILABLE = False
    LDAPException = Exception
    LDAPBindError = Exception
    LDAPInvalidCredentialsResult = Exception

    def escape_filter_chars(value):  # type: ignore[misc]
        return value


def parse_ldap_url(url: str):
    """Split ``ldap[s]://host:port`` into ``(host, port, use_ssl)``."""
    scheme, separator, rest = (url or "").partition("://")
    if not separator:
        scheme, rest = "ldap", url or ""
    scheme = scheme.strip().lower()
    use_ssl = scheme == "ldaps"

    rest = rest.strip().rstrip("/")
    if ":" in rest and not rest.startswith("["):
        host, _, port_text = rest.rpartition(":")
        try:
            port = int(port_text)
        except ValueError:
            host, port = rest, 636 if use_ssl else 389
    else:
        host, port = rest, 636 if use_ssl else 389

    return host, port, use_ssl


class LdapAuthProvider(AuthProvider):
    name = "ldap"

    def __init__(self, cfg):
        self.cfg = cfg
        self.host, self.port, self.use_ssl = parse_ldap_url(cfg.LDAP_URL)

    # ------------------------------------------------------------------ setup

    def available(self) -> bool:
        return bool(LDAP3_AVAILABLE and self.host and self.cfg.LDAP_BASE_DN)

    def describe(self) -> dict:
        return {
            "name": self.name,
            "available": self.available(),
            "url": f"{'ldaps' if self.use_ssl else 'ldap'}://{self.host}:{self.port}",
            "starttls": bool(self.cfg.LDAP_STARTTLS),
        }

    def _tls(self):
        if not (self.use_ssl or self.cfg.LDAP_STARTTLS):
            return None
        if self.cfg.LDAP_INSECURE and not self.cfg.LDAP_CA_CERT:
            return Tls(validate=ssl.CERT_NONE)
        options = {"validate": ssl.CERT_REQUIRED}
        if self.cfg.LDAP_CA_CERT:
            options["ca_certs_file"] = self.cfg.LDAP_CA_CERT
        return Tls(**options)

    def _server(self):
        return Server(
            self.host,
            port=self.port,
            use_ssl=self.use_ssl,
            get_info=NONE,
            tls=self._tls(),
            connect_timeout=self.cfg.LDAP_TIMEOUT,
        )

    def _connect(self, bind_dn: str, bind_password: str, purpose: str):
        """Open + optionally StartTLS + bind. Raises AuthError when unusable.

        ``raise_exceptions=True`` is used deliberately. ldap3 returns ``None``
        from ``open()`` even on success (only failures are reported through the
        return value, and only when exceptions are suppressed), so treating that
        return value as a boolean rejects every working directory. Letting ldap3
        raise gives precise, catchable failures instead.
        """
        try:
            connection = Connection(
                self._server(),
                user=bind_dn or None,
                password=bind_password or None,
                auto_bind=False,
                raise_exceptions=True,
                receive_timeout=self.cfg.LDAP_TIMEOUT,
            )
            connection.open()

            if self.cfg.LDAP_STARTTLS and not self.use_ssl:
                connection.start_tls()

            try:
                bound = connection.bind()
            except (LDAPInvalidCredentialsResult, LDAPBindError):
                # Rejected credentials are an authentication outcome, not a
                # server fault: the caller decides what it means.
                return connection, False

            return connection, bool(bound)
        except AuthError:
            raise
        except LDAPException as exc:
            logger.warning("LDAP %s failed: %s", purpose, exc)
            raise AuthError(f"Directory server error ({purpose})", 503) from exc
        except Exception as exc:  # socket, TLS, DNS
            logger.warning("LDAP %s failed: %s", purpose, exc)
            raise AuthError(f"Directory server is unreachable ({purpose})", 503) from exc

    # ----------------------------------------------------------- authenticate

    def authenticate(self, username: str, password: str):
        if not LDAP3_AVAILABLE:
            raise AuthError("LDAP support is not installed in this image", 503)
        if not self.available():
            raise AuthError("LDAP is not configured", 503)

        username = (username or "").strip()
        # Never let a blank password reach the server: that is an unauthenticated bind.
        if not username or not password:
            return None

        entry = self._find_user(username)
        if entry is None:
            logger.info("LDAP: no entry matched username %r", username)
            return None

        user_dn = entry.entry_dn
        if not self._verify_password(user_dn, password):
            logger.info("LDAP: bind failed for %r", user_dn)
            return None

        groups = self._groups(entry, user_dn)
        role = self._role(groups)
        # Logged because "why is this user not an admin?" is the most common
        # support question, and it always comes down to group mapping.
        logger.info(
            "LDAP: authenticated %r (dn=%s) groups=%s -> role=%s",
            username,
            user_dn,
            groups or "[]",
            role,
        )
        return User(
            username=self._attr(entry, self.cfg.LDAP_ATTR_USERNAME) or username,
            role=role,
            display_name=self._attr(entry, self.cfg.LDAP_ATTR_DISPLAY) or username,
            email=self._attr(entry, self.cfg.LDAP_ATTR_MAIL),
            provider=self.name,
            groups=groups,
        )

    def _user_filter(self, username: str) -> str:
        """Build the search filter, escaping the username against LDAP injection."""
        template = self.cfg.LDAP_USER_FILTER or "({attr}={username})"
        escaped = escape_filter_chars(username)
        if "{username}" in template or "{user}" in template:
            return template.replace("{username}", escaped).replace("{user}", escaped)
        # A filter with no placeholder is treated as a requirement, not a whole
        # filter, so that operators can write `(objectClass=person)`.
        return f"(&{template}({self.cfg.LDAP_ATTR_USERNAME}={escaped}))"

    def _find_user(self, username: str):
        """Service-account search for the user's entry."""
        search_filter = self._user_filter(username)

        attributes = [
            self.cfg.LDAP_ATTR_USERNAME,
            self.cfg.LDAP_ATTR_MAIL,
            self.cfg.LDAP_ATTR_DISPLAY,
            "memberOf",
        ]

        connection, bound = self._connect(
            self.cfg.LDAP_BIND_DN, self.cfg.LDAP_BIND_PASSWORD, "service bind"
        )
        try:
            # An anonymous bind is only attempted when no service account is set.
            if not bound and self.cfg.LDAP_BIND_DN:
                raise AuthError("Directory service account credentials were rejected", 503)

            if not connection.search(
                search_base=self.cfg.LDAP_USER_BASE or self.cfg.LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=2,
            ):
                logger.info("LDAP: search for %r returned no result (%s)", username, connection.result)
                return None

            entries = connection.entries
            if not entries:
                return None
            if len(entries) > 1:
                # Ambiguous identity: refuse rather than guess which one to log in.
                logger.warning("LDAP: username %r matched more than one entry", username)
                raise AuthError("Username is ambiguous in the directory", 409)
            return entries[0]
        finally:
            try:
                connection.unbind()
            except Exception:
                pass

    def _verify_password(self, user_dn: str, password: str) -> bool:
        connection, bound = self._connect(user_dn, password, "user bind")
        try:
            return bound
        finally:
            try:
                connection.unbind()
            except Exception:
                pass

    # --------------------------------------------------------------- groups

    def _groups(self, entry, user_dn: str) -> list:
        groups = []

        # OpenLDAP with the memberOf overlay, and Active Directory, expose groups
        # directly on the user entry.
        try:
            if "memberOf" in entry:
                values = entry["memberOf"].values
                groups.extend(values if isinstance(values, (list, tuple)) else [values])
        except Exception:
            pass

        # Without the overlay (our own container has memberOf off by default) the
        # groups must be searched for. Requires LDAP_GROUP_FILTER.
        if self.cfg.LDAP_GROUP_FILTER:
            groups.extend(self._search_groups(entry, user_dn))

        return sorted({g for g in groups if g})

    def _search_groups(self, entry, user_dn: str) -> list:
        escaped_dn = escape_filter_chars(user_dn)
        escaped_user = escape_filter_chars(self._attr(entry, self.cfg.LDAP_ATTR_USERNAME))
        search_filter = (
            self.cfg.LDAP_GROUP_FILTER.replace("{user_dn}", escaped_dn).replace(
                "{username}", escaped_user
            )
        )

        connection, bound = self._connect(
            self.cfg.LDAP_BIND_DN, self.cfg.LDAP_BIND_PASSWORD, "group search"
        )
        try:
            if not bound and self.cfg.LDAP_BIND_DN:
                return []
            if not connection.search(
                search_base=self.cfg.LDAP_GROUP_BASE or self.cfg.LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["cn"],
            ):
                return []
            found = []
            for group in connection.entries:
                try:
                    found.append(group.entry_dn)
                except Exception:
                    continue
            return found
        finally:
            try:
                connection.unbind()
            except Exception:
                pass

    def _role(self, groups) -> str:
        if self._matches_admin(groups):
            return ROLE_ADMIN
        return self.cfg.DEFAULT_ROLE or ROLE_VIEWER

    def _matches_admin(self, groups) -> bool:
        configured = split_group_list(self.cfg.LDAP_ADMIN_GROUP)
        return matches_group(configured, groups)

    @staticmethod
    def _attr(entry, name: str) -> str:
        try:
            if name in entry:
                value = entry[name].value
                return str(value).strip() if value is not None else ""
        except Exception:
            pass
        return ""
