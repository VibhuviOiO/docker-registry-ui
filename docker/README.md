# Docker examples

Run each example from its own directory. Examples with `build: context: ../..`
require a checkout of this repository; that path points to the repository root.

| Example | Configuration |
|---|---|
| [Built-in Trivy](built-in-trivy/docker-compose.yml) | Inline `REGISTRIES` environment variable |
| [Remote Trivy](remote-trivy/docker-compose.yml) | Inline `REGISTRIES` environment variable |
| [Multiple registries](multi-registry/docker-compose.yml) | `multi-registry/registries.config.json` |
| [Basic authentication](basic-auth/docker-compose.yml) | `basic-auth/registries.config.json` |
| [LDAP sign-in](ldap-auth/docker-compose.yml) | Inline `REGISTRIES`; LDAP authenticates UI users |

## Connection settings

Registry settings belong inside each registry object, whether it is stored in
a JSON file or the `REGISTRIES` environment variable. They are not standalone
container environment variables.

| Field | Meaning |
|---|---|
| `auth.type` | `none` for anonymous access, `basic` for username/password with Bearer challenge support, or `bearer` for a fixed Registry token |
| `allowHttp` | Allow HTTP Bearer token endpoints and cross-host credential delegation from an HTTP Registry; defaults to `false` |
| `skipTlsVerify` | Skip TLS certificate verification for the Registry and its token service; defaults to `false` |

All runnable examples keep both connection options `false`. Local Registry API
addresses such as `http://registry:5000` work without enabling `allowHttp` because
these examples have no HTTP Bearer token service. `skipTlsVerify` does not affect
an HTTP connection. Neither setting changes Trivy's TLS configuration or LDAP
sign-in settings.

For a Registry whose Bearer challenge advertises an HTTP token service, enable
`allowHttp` on that Registry. For example:

```json
{
  "name": "HTTP Registry with token authentication",
  "api": "http://registry.example.com:5000",
  "auth": {
    "type": "basic",
    "username": "registry-user",
    "password": "replace-with-registry-password"
  },
  "allowHttp": true,
  "skipTlsVerify": false
}
```

For an HTTPS Registry with an untrusted certificate, `skipTlsVerify` can disable
certificate verification. It applies to both the Registry and its token service:

```json
{
  "name": "Registry with an untrusted certificate",
  "api": "https://registry.example.com",
  "auth": {
    "type": "basic",
    "username": "registry-user",
    "password": "replace-with-registry-password"
  },
  "allowHttp": false,
  "skipTlsVerify": true
}
```

These two illustrative objects require an existing Registry and belong in the
configuration's registry array. They do not deploy a token service or generate
certificates. HTTP can expose credentials or tokens in transit, and disabling
certificate verification permits impersonation. Token-service redirects remain
disabled even when these options are enabled.

The local examples retain anonymous access; the Basic authentication example
uses `auth.type: basic` for its protected Registry. Registry credentials are
separate from LDAP or SSO credentials used to sign in to the UI.
