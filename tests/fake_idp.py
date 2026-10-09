"""A minimal, real OpenID Connect provider for tests.

Serves a discovery document, a JWKS and a token endpoint over real HTTP on
localhost, and signs real RS256 id_tokens with a real RSA key. Mocking the
identity provider would not exercise the parts most likely to be wrong --
discovery parsing, JWKS key selection, signature verification, claim validation
-- so this runs an actual HTTP server instead.
"""

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm


class FakeIdP:
    CLIENT_ID = "docker-registry-ui"
    CLIENT_SECRET = "test-client-secret"

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "test-key-1"
        self.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_kid = "test-key-2"

        self.issuer = ""  # filled in once the server has bound a port
        self.port = None

        # Knobs the tests use to simulate provider behaviour.
        self.include_other_key = False
        self.token_status = 200
        self.mint = self._default_mint
        self.omit_id_token = False

        self.issued = {}  # authorization code -> claims
        self.token_requests = []
        self.jwks_calls = 0

        # Claims handed to whoever completes the authorization endpoint. Swap
        # this out to log in as a different user or role.
        self.authorize_claims = self._default_authorize_claims

        self._httpd = None
        self._thread = None

    def _default_authorize_claims(self) -> dict:
        return {
            "sub": "subject-alice",
            "preferred_username": "alice",
            "name": "Alice Example",
            "email": "alice@example.com",
            "groups": ["registry-admins"],
        }

    # ------------------------------------------------------------------ keys

    @staticmethod
    def _jwk(key, kid):
        jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
        return jwk

    def jwks(self) -> dict:
        self.jwks_calls += 1
        keys = [self._jwk(self.key, self.kid)]
        if self.include_other_key:
            keys.append(self._jwk(self.other_key, self.other_kid))
        return {"keys": keys}

    # ----------------------------------------------------------------- tokens

    def mint_id_token(self, claims, key=None, kid=None, algorithm="RS256"):
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "aud": self.CLIENT_ID,
            "iat": now,
            "exp": now + 300,
        }
        payload.update(claims)
        return jwt.encode(
            payload,
            key if key is not None else self.key,
            algorithm=algorithm,
            headers={"kid": kid if kid is not None else self.kid},
        )

    def issue_code(self, code: str, claims: dict) -> None:
        self.issued[code] = claims

    def _default_mint(self, form):
        code = (form.get("code") or [""])[0]
        return self.mint_id_token(self.issued.get(code, {}))

    # ----------------------------------------------------------------- server

    def start(self):
        idp = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # keep test output clean
                pass

            def _send(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorize(self):
                """Issue a code and redirect back, like a real provider."""
                query = parse_qs(urlparse(self.path).query)
                redirect_uri = (query.get("redirect_uri") or [""])[0]
                state = (query.get("state") or [""])[0]
                nonce = (query.get("nonce") or [""])[0]

                if not redirect_uri:
                    self._send(400, {"error": "invalid_request"})
                    return

                code = "code-" + uuid.uuid4().hex
                claims = dict(idp.authorize_claims() or {})
                claims["nonce"] = nonce
                idp.issued[code] = claims

                target = f"{redirect_uri}?code={quote(code)}&state={quote(state)}"
                self.send_response(302)
                self.send_header("Location", target)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/.well-known/openid-configuration":
                    self._send(
                        200,
                        {
                            "issuer": idp.issuer,
                            "authorization_endpoint": f"{idp.issuer}/authorize",
                            "token_endpoint": f"{idp.issuer}/token",
                            "jwks_uri": f"{idp.issuer}/jwks",
                            "response_types_supported": ["code"],
                            "subject_types_supported": ["public"],
                            "id_token_signing_alg_values_supported": ["RS256"],
                        },
                    )
                elif path == "/jwks":
                    self._send(200, idp.jwks())
                elif path == "/authorize":
                    self._authorize()
                else:
                    self._send(404, {"error": "not_found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8")
                form = parse_qs(raw)

                if self.path.split("?")[0] != "/token":
                    self._send(404, {"error": "not_found"})
                    return

                idp.token_requests.append(form)

                if idp.token_status != 200:
                    self._send(idp.token_status, {"error": "invalid_grant"})
                    return

                if form.get("client_id", [""])[0] != idp.CLIENT_ID:
                    self._send(400, {"error": "invalid_client"})
                    return
                if form.get("client_secret", [""])[0] != idp.CLIENT_SECRET:
                    self._send(401, {"error": "invalid_client"})
                    return

                response = {"access_token": "access-token", "token_type": "Bearer"}
                if not idp.omit_id_token:
                    response["id_token"] = idp.mint(form)
                self._send(200, response)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self.issuer = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
