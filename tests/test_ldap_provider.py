"""LDAP provider unit tests that need no server.

The security-relevant behaviour (filter escaping, empty-password rejection,
group-to-role mapping) is all testable in isolation, which is the point: these
paths are easy to regress and hard to notice.
"""

import pytest

from app.auth.config import AuthConfig
from app.auth.models import ROLE_ADMIN, ROLE_VIEWER, AuthError
from app.auth.providers.ldap import LdapAuthProvider, parse_ldap_url


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    AuthConfig.load()
    return LdapAuthProvider(AuthConfig)


# ------------------------------------------------------------------- URL parsing


@pytest.mark.parametrize(
    "url,expected",
    [
        ("ldap://host.example.com:389", ("host.example.com", 389, False)),
        ("ldaps://host.example.com:636", ("host.example.com", 636, True)),
        ("ldaps://host.example.com", ("host.example.com", 636, True)),
        ("ldap://host.example.com", ("host.example.com", 389, False)),
        ("host.example.com:1389", ("host.example.com", 1389, False)),
        ("host.example.com", ("host.example.com", 389, False)),
    ],
)
def test_parse_ldap_url(url, expected):
    assert parse_ldap_url(url) == expected


# --------------------------------------------------------------- authentication


def test_empty_password_never_reaches_the_directory(provider, monkeypatch):
    """An empty LDAP bind succeeds as an unauthenticated bind on most servers.

    If this ever regressed, a blank password field would be a valid login.
    """

    def explode(*args, **kwargs):
        raise AssertionError("the directory must not be searched with an empty password")

    monkeypatch.setattr(provider, "_find_user", explode)
    assert provider.authenticate("someone", "") is None


def test_blank_username_is_rejected_without_a_search(provider, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("the directory must not be searched with a blank username")

    monkeypatch.setattr(provider, "_find_user", explode)
    assert provider.authenticate("   ", "password") is None


def test_unreachable_directory_raises_503_not_bad_credentials(monkeypatch):
    monkeypatch.setenv("LDAP_URL", "ldap://127.0.0.1:1")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setenv("LDAP_TIMEOUT", "2")
    AuthConfig.load()

    with pytest.raises(AuthError) as excinfo:
        LdapAuthProvider(AuthConfig).authenticate("someone", "password")

    assert excinfo.value.status_code == 503


# ------------------------------------------------------------- filter injection


def test_username_is_escaped_in_the_search_filter(provider):
    hostile = "admin)(|(uid=*"
    search_filter = provider._user_filter(hostile)

    # The raw metacharacters must not survive unescaped.
    assert ")(|(uid=*" not in search_filter
    assert "\\29" in search_filter  # escaped ')'
    assert "\\28" in search_filter  # escaped '('
    assert "\\2a" in search_filter  # escaped '*'


def test_default_filter_uses_the_username_placeholder(provider):
    assert provider._user_filter("alice") == "(&(objectClass=inetOrgPerson)(uid=alice))"


def test_filter_without_placeholder_is_treated_as_a_requirement(provider, monkeypatch):
    monkeypatch.setenv("LDAP_USER_FILTER", "(objectClass=person)")
    AuthConfig.load()
    provider = LdapAuthProvider(AuthConfig)

    assert provider._user_filter("alice") == "(&(objectClass=person)(uid=alice))"


# ------------------------------------------------------------------ role mapping


def test_default_role_is_viewer(monkeypatch):
    monkeypatch.setenv("LDAP_URL", "ldap://host:389")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setenv("LDAP_ADMIN_GROUP", "cn=registry-admins,ou=Group,dc=example,dc=com")
    AuthConfig.load()
    provider = LdapAuthProvider(AuthConfig)

    assert provider._role(["cn=other,ou=Group,dc=example,dc=com"]) == ROLE_VIEWER


def test_admin_group_matches_by_full_dn(monkeypatch):
    monkeypatch.setenv("LDAP_URL", "ldap://host:389")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setenv("LDAP_ADMIN_GROUP", "cn=registry-admins,ou=Group,dc=example,dc=com")
    AuthConfig.load()
    provider = LdapAuthProvider(AuthConfig)

    groups = ["CN=Registry-Admins,OU=Group,DC=Example,DC=Com"]
    assert provider._role(groups) == ROLE_ADMIN


def test_admin_group_matches_by_common_name(monkeypatch):
    monkeypatch.setenv("LDAP_URL", "ldap://host:389")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setenv("LDAP_ADMIN_GROUP", "registry-admins")
    AuthConfig.load()
    provider = LdapAuthProvider(AuthConfig)

    assert provider._role(["cn=registry-admins,ou=Group,dc=example,dc=com"]) == ROLE_ADMIN


def test_multiple_admin_groups(monkeypatch):
    """Multiple groups are separated by ';' because commas belong to DNs."""
    monkeypatch.setenv("LDAP_URL", "ldap://host:389")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setenv("LDAP_ADMIN_GROUP", "platform;registry-admins")
    AuthConfig.load()
    provider = LdapAuthProvider(AuthConfig)

    assert provider._role(["cn=platform,ou=Group,dc=example,dc=com"]) == ROLE_ADMIN
    assert provider._role(["cn=registry-admins,ou=Group,dc=example,dc=com"]) == ROLE_ADMIN
    assert provider._role(["cn=developers,ou=Group,dc=example,dc=com"]) == ROLE_VIEWER


def test_dn_form_admin_group_is_not_split_on_commas():
    """Regression: splitting on ',' shredded DN-form group names."""
    from app.auth.providers.ldap import split_group_list

    dn = "cn=registry-admins,ou=Group,dc=example,dc=com"
    assert split_group_list(dn) == [dn]

    both = f"{dn};cn=platform,ou=Group,dc=example,dc=com"
    assert split_group_list(both) == [
        dn,
        "cn=platform,ou=Group,dc=example,dc=com",
    ]

    assert split_group_list("") == []
    assert split_group_list("  ") == []


def test_unknown_role_falls_back_to_viewer():
    """A typo in AUTH_DEFAULT_ROLE must never grant more access."""
    from app.auth.models import normalise_role

    assert normalise_role("administrator") == ROLE_VIEWER
    assert normalise_role("") == ROLE_VIEWER
    assert normalise_role("ADMIN") == ROLE_ADMIN
