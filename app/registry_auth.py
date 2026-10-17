"""Registry V2 Bearer challenges, including anonymous token exchange."""

from functools import partial
import re
from urllib.parse import urlsplit
from urllib.request import parse_http_list

import requests
from requests.auth import AuthBase, HTTPBasicAuth
from requests.utils import parse_dict_header


def _origin(url):
    parsed = urlsplit(url)
    return parsed.scheme.lower(), parsed.hostname, parsed.port or (
        443 if parsed.scheme.lower() == "https" else 80
    )


def _bearer_challenge(header):
    # Split outside quoted strings: scope="repository:team/image:pull,push"
    # is one parameter. A header can also contain multiple auth schemes.
    parameters = []
    in_bearer = False
    for part in parse_http_list(header):
        scheme = re.match(r"^([\w!#$%&'*+.^`|~-]+)\s+(.*)$", part)
        if scheme and not scheme[2].lstrip().startswith("="):
            if in_bearer:
                break
            in_bearer = scheme[1].lower() == "bearer"
            if in_bearer:
                parameters.append(scheme[2])
        elif in_bearer:
            parameters.append(part)
    # Requests' parser does not trim whitespace around the equals sign.
    parameters = ["=".join(piece.strip() for piece in parameter.split("=", 1))
                  for parameter in parameters]
    return {key.lower(): value for key, value in
            parse_dict_header(",".join(parameters)).items()}


class RegistryHeaders(dict):
    """Fixed authorization headers with the registry's TLS setting."""

    def __init__(self, headers, skip_tls_verify=False):
        super().__init__(headers)
        self.skip_tls_verify = skip_tls_verify


def registry_request_options(auth):
    return {"verify": False} if getattr(auth, "skip_tls_verify", False) else {}


class RegistryAuth(AuthBase):
    def __init__(self, username=None, password=None, *, allow_http=False, skip_tls_verify=False):
        self.basic = HTTPBasicAuth(username, password) if username and password else None
        self.allow_http = allow_http
        self.skip_tls_verify = skip_tls_verify

    def __call__(self, request):
        # Preserve preemptive Basic authentication for existing registries.
        if self.basic:
            self.basic(request)
        request.register_hook(
            "response", partial(self._handle_response, origin=_origin(request.url))
        )
        return request

    def _handle_response(self, response, origin, **kwargs):
        # Requests preserves hooks across redirects, including cross-origin ones.
        if response.status_code != 401 or _origin(response.request.url) != origin:
            return response

        challenge = _bearer_challenge(response.headers.get("WWW-Authenticate", ""))
        realm = challenge.get("realm")
        if not realm:
            return response
        target = urlsplit(realm)
        allowed_schemes = ("https", "http") if self.allow_http else ("https",)
        if (target.scheme.lower() not in allowed_schemes or not target.hostname
                or target.username is not None or target.password is not None
                or target.fragment
                or (kwargs.get("verify") is False and not self.skip_tls_verify)):
            return response
        # Cross-host credential delegation from HTTP requires explicit opt-in.
        if (self.basic and origin[0] != "https" and target.hostname != origin[1]
                and not self.allow_http):
            return response

        params = {key: challenge[key] for key in ("service", "scope")
                  if challenge.get(key) is not None}
        # Release the initial connection before requesting the token/retrying.
        response.content
        response.close()
        with requests.get(
            realm, params=params, auth=self.basic or (lambda request: request),
            timeout=kwargs.get("timeout") or 10,
            verify=False if self.skip_tls_verify else kwargs.get("verify", True),
            # Resolve environment proxies for the token URL, including NO_PROXY.
            allow_redirects=False,
        ) as token_response:
            if token_response.status_code != 200:
                return response
            try:
                payload = token_response.json()
            except ValueError:
                return response
            if not isinstance(payload, dict):
                return response
            token = payload.get("token") or payload.get("access_token")
            if not isinstance(token, str) or not token or "\r" in token or "\n" in token:
                return response

        retry = response.request.copy()
        retry.headers["Authorization"] = f"Bearer {token}"
        # Adapter.send does not dispatch response hooks: at most one retry.
        result = response.connection.send(retry, **kwargs)
        result.history = list(response.history) + [response]
        return result
