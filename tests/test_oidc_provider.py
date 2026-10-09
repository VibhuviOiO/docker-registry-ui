"""OIDC provider tests, run against the real fake identity provider.

These exercise the parts most likely to be wrong and most damaging if wrong:
signature verification, algorithm confusion, claim validation, nonce binding and
group-to-role mapping.
"""

import base64
import hashlib

import pytest

from app.auth.config import AuthConfig
from app.auth.models import ROLE_ADMIN, ROLE_VIEWER, AuthError
from app.auth.providers.oidc import OidcAuthProvider, create_pkce_pair

NONCE = "nonce-abc123"


@pytest.fixture
def provider(oidc_env):
    AuthConfig.load()
    return OidcAuthProvider(AuthConfig)


def claims(**extra):
    base = {
        "sub": "user-123",
        "preferred_username": "alice",
        "name": "Alice Example",
        "email": "alice@example.com",
        "nonce": NONCE,
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------- PKCE


def test_pkce_challenge_is_the_s256_digest_of_the_verifier():
    verifier, challenge = create_pkce_pair()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert challenge == expected
    # RFC 7636 requires 43..128 characters.
    assert 43 <= len(verifier) <= 128
    assert "=" not in challenge


# ------------------------------------------------------------ happy path


def test_exchange_maps_admin_group_to_admin_role(provider, idp):
    idp.issue_code("code-admin", claims(groups=["registry-admins", "developers"]))
    user = provider.exchange_code("code-admin", "verifier", NONCE)

    assert user.username == "alice"
    assert user.role == ROLE_ADMIN
    assert user.display_name == "Alice Example"
    assert user.email == "alice@example.com"
    assert user.provider == "oidc"

    # The PKCE verifier must actually be sent to the token endpoint.
    assert idp.token_requests[-1]["code_verifier"] == ["verifier"]
    assert idp.token_requests[-1]["grant_type"] == ["authorization_code"]


def test_non_member_gets_the_default_role(provider, idp):
    idp.issue_code("code-viewer", claims(groups=["developers"]))
    user = provider.exchange_code("code-viewer", "verifier", NONCE)
    assert user.role == ROLE_VIEWER


def test_missing_groups_claim_falls_back_to_the_default_role(provider, idp):
    idp.issue_code("code-nogroups", claims())
    user = provider.exchange_code("code-nogroups", "verifier", NONCE)
    assert user.role == ROLE_VIEWER


def test_group_matching_is_case_insensitive(provider, idp):
    idp.issue_code("code-case", claims(groups=["Registry-Admins"]))
    assert provider.exchange_code("code-case", "verifier", NONCE).role == ROLE_ADMIN


def test_username_falls_back_to_email_then_subject(provider, idp):
    idp.issue_code("code-email", claims(preferred_username="", email="e@example.com"))
    assert provider.exchange_code("code-email", "verifier", NONCE).username == "e@example.com"

    idp.issue_code("code-sub", claims(preferred_username="", email="", sub="subject-9"))
    assert provider.exchange_code("code-sub", "verifier", NONCE).username == "subject-9"


def test_authorization_url_carries_state_nonce_and_pkce(provider):
    url = provider.authorization_url("state-1", "nonce-1", "challenge-1")
    assert url.startswith(f"{provider.cfg.OIDC_ISSUER}/authorize?")
    assert "response_type=code" in url
    assert "state=state-1" in url
    assert "nonce=nonce-1" in url
    assert "code_challenge=challenge-1" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=docker-registry-ui" in url
    # Must be the browser-facing URL, not an internal one.
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Foidc%2Fcallback" in url


# --------------------------------------------------------- token validation


def test_nonce_mismatch_is_rejected(provider, idp):
    idp.issue_code("code-badnonce", claims(nonce="a-different-nonce"))
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-badnonce", "verifier", NONCE)
    assert excinfo.value.status_code == 401
    assert "nonce" in excinfo.value.message.lower()


def test_missing_nonce_is_rejected(provider, idp):
    idp.issue_code("code-nononce", claims(nonce=""))
    with pytest.raises(AuthError):
        provider.exchange_code("code-nononce", "verifier", NONCE)


def test_wrong_audience_is_rejected(provider, idp):
    idp.issue_code("code-aud", claims(aud="some-other-application"))
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-aud", "verifier", NONCE)
    assert excinfo.value.status_code == 401


def test_wrong_issuer_is_rejected(provider, idp):
    idp.issue_code("code-iss", claims(iss="http://attacker.example.com"))
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-iss", "verifier", NONCE)
    assert excinfo.value.status_code == 401


def test_token_signed_by_the_wrong_key_is_rejected(provider, idp):
    """Right key id, wrong private key: the signature must not verify."""
    idp.issue_code("code-forged", claims())
    idp.mint = lambda form: idp.mint_id_token(
        claims(), key=idp.other_key, kid=idp.kid
    )
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-forged", "verifier", NONCE)
    assert excinfo.value.status_code == 401


def test_hs256_signed_token_is_refused(provider, idp):
    """Algorithm confusion: signing with the client secret must not be accepted."""
    idp.issue_code("code-hs", claims())
    idp.mint = lambda form: idp.mint_id_token(
        claims(), key=idp.CLIENT_SECRET, algorithm="HS256"
    )
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-hs", "verifier", NONCE)
    assert "algorithm" in excinfo.value.message.lower()


def test_unsigned_token_is_refused(provider, idp):
    import jwt as pyjwt

    idp.issue_code("code-none", claims())
    idp.mint = lambda form: pyjwt.encode(
        claims(), key=None, algorithm="none", headers={"kid": idp.kid}
    )
    with pytest.raises(AuthError):
        provider.exchange_code("code-none", "verifier", NONCE)


def test_expired_token_is_rejected(provider, idp):
    import time

    idp.issue_code("code-exp", claims())
    idp.mint = lambda form: idp.mint_id_token(
        {**claims(), "exp": int(time.time()) - 60}
    )
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-exp", "verifier", NONCE)
    assert excinfo.value.status_code == 401


def test_rotated_signing_key_is_picked_up_after_a_jwks_refresh(provider, idp):
    """A provider that rotates keys must not lock everyone out."""
    # Prime the JWKS cache with a successful exchange using the first key.
    idp.issue_code("code-primer", claims(groups=["registry-admins"]))
    provider.exchange_code("code-primer", "verifier", NONCE)
    calls_before = idp.jwks_calls

    # The provider rotates: the new key appears only in a fresh JWKS.
    idp.include_other_key = True
    idp.issue_code("code-rotated", claims())
    idp.mint = lambda form: idp.mint_id_token(
        claims(), key=idp.other_key, kid=idp.other_kid
    )

    user = provider.exchange_code("code-rotated", "verifier", NONCE)
    assert user.username == "alice"
    assert idp.jwks_calls > calls_before, "the provider should have refreshed its JWKS"


# ------------------------------------------------------------ provider errors


def test_token_endpoint_error_is_reported_as_a_failed_login(provider, idp):
    idp.token_status = 400
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-err", "verifier", NONCE)
    assert excinfo.value.status_code == 401


def test_missing_id_token_is_rejected(provider, idp):
    idp.omit_id_token = True
    with pytest.raises(AuthError) as excinfo:
        provider.exchange_code("code-noid", "verifier", NONCE)
    assert "id_token" in excinfo.value.message


def test_unreachable_provider_is_a_503_not_a_401(monkeypatch, isolated_data_dir):
    monkeypatch.setenv("OIDC_ISSUER", "http://127.0.0.1:1")
    monkeypatch.setenv("OIDC_CLIENT_ID", "x")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "y")
    monkeypatch.setenv("AUTH_PUBLIC_URL", "http://testserver")
    monkeypatch.setenv("OIDC_TIMEOUT", "2")
    AuthConfig.load()

    with pytest.raises(AuthError) as excinfo:
        OidcAuthProvider(AuthConfig).metadata()
    assert excinfo.value.status_code == 503


def test_password_login_is_refused_in_oidc_mode(provider):
    with pytest.raises(AuthError) as excinfo:
        provider.authenticate("alice", "password")
    assert excinfo.value.status_code == 400


def test_unavailable_reason_names_the_missing_settings(isolated_data_dir):
    AuthConfig.load()  # conftest has cleared every OIDC variable
    provider = OidcAuthProvider(AuthConfig)

    assert provider.available() is False
    reason = provider.unavailable_reason()
    for name in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "AUTH_PUBLIC_URL"):
        assert name in reason
