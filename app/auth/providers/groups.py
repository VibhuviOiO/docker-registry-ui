"""Group / claim to role matching, shared by the LDAP and OIDC providers.

Both providers answer the same question -- "is this user in an admin group?" --
against values that may be LDAP DNs, bare group names, or SSO claim strings.
Keeping the comparison in one place means a fix or a subtlety cannot land in one
provider and be missed in the other.
"""

import re

_WHITESPACE = re.compile(r"\s+")


def normalise_dn(value: str) -> str:
    """Case- and whitespace-insensitive form, so DN comparison is reliable."""
    return _WHITESPACE.sub("", value or "").lower()


def split_group_list(value: str) -> list:
    """Split a configured group list.

    Separators are ``;`` and newlines. A comma is deliberately **not** a
    separator: commas occur inside DNs, so splitting on them would shred
    ``cn=registry-admins,ou=Group,dc=example,dc=com`` into four fragments and
    the admin group could never match.
    """
    return [item.strip() for item in re.split(r"[;\n]", value or "") if item.strip()]


def first_rdn_value(dn: str) -> str:
    """Return the leading value of a DN or a bare name.

    ``cn=registry-admins,ou=Group,...`` -> ``registry-admins``
    ``registry-admins``                 -> ``registry-admins``
    """
    first = (dn or "").split(",")[0].strip()
    if "=" in first:
        first = first.split("=", 1)[1]
    return first.strip().lower()


def as_group_list(value) -> list:
    """Normalise a claim value into a list of group names.

    Identity providers disagree on shape: a list, a single string, a
    comma/space separated string, or a Keycloak-style mapping.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in re.split(r"[,\s]+", value) if part]
    if isinstance(value, dict):
        # Keycloak puts group paths under the "groups" key of a claim dict.
        collected = []
        for item in value.values():
            collected.extend(as_group_list(item))
        return collected
    if isinstance(value, (list, tuple, set)):
        collected = []
        for item in value:
            if isinstance(item, str):
                collected.append(item)
            else:
                collected.extend(as_group_list(item))
        return collected
    return [str(value)]


def matches_group(configured, groups) -> bool:
    """Whether any configured group matches any of the user's groups.

    A configured entry containing ``=`` is compared as a DN; anything else is
    compared as a bare name against the leading RDN value. Both comparisons are
    case-insensitive, because directories and IdPs are inconsistent about case.
    """
    wanted = [item for item in (configured or []) if item]
    if not wanted or not groups:
        return False

    normalised = {normalise_dn(g) for g in groups}
    short = {first_rdn_value(g) for g in groups}

    for candidate in wanted:
        if "=" in candidate:
            if normalise_dn(candidate) in normalised:
                return True
        elif candidate.strip().lower() in short or normalise_dn(candidate) in normalised:
            return True
    return False
