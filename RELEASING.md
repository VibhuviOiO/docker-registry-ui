# Releasing

Two phases, deliberately separate:

| Phase | Trigger | What runs |
|---|---|---|
| Test | Push to any branch, or a pull request | [`ci.yml`](.github/workflows/ci.yml) — unit + integration tests, Docker image build, and a full end-to-end run against a real OpenLDAP and registry |
| Release | A tag you push by hand | [`release.yml`](.github/workflows/release.yml), [`docker-publish.yml`](.github/workflows/docker-publish.yml), [`dockerhub-publish.yml`](.github/workflows/dockerhub-publish.yml) |

Pushing to `main` publishes nothing. **Tags are never created by CI** — the
release workflows fail rather than create one.

## 1. Test the branch

Nothing to do: CI runs on every push. Check it before you release:

```bash
gh run list --branch v2.2-development --limit 5
```

Run the same checks locally:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q                    # unit + integration

cd docker/ldap-auth
docker compose up -d --no-build openldap ldap-bootstrap registry
cd ../.. && python tests/validate_full_stack.py   # end-to-end, exit 0 = pass
```

## 2. Write the release notes

This is a required step, not a nicety: the publish workflows refuse a tag whose
version has no `CHANGELOG.md` section, and that section becomes the body of the
GitHub release.

```bash
$EDITOR CHANGELOG.md     # move entries from "Unreleased" into "## [2.2.0]"
bash -c './venv/bin/python scripts/extract_release_notes.py 2.2.0'   # preview the body
```

## 3. Bump the version and commit

`app/version.py` is the only place the version lives.

```bash
$EDITOR app/version.py   # __version__ = "2.2.0"
git commit -am "release: v2.2.0 — LDAP/AD and SSO authentication, audit log"
git push origin v2.2-development
```

## 4. Tag and push the tag

```bash
git tag v2.2.0
git push origin v2.2.0
```

The tag must equal `app/version.py` exactly (with an optional `v` prefix) or the
release fails. That publishes:

- `ghcr.io/vibhuvioio/docker-registry-ui:2.2.0` and `:latest`
- `vibhuvioio/docker-registry-ui:2.2.0` and `:latest`
- a GitHub release titled `v2.2.0`, with the changelog section as its body

Check it:

```bash
gh release view v2.2.0
docker run --rm vibhuvioio/docker-registry-ui:2.2.0 --help >/dev/null && echo pulled
```

## If a release fails

Fix forward, do not move the tag:

1. Fix the problem on `main`.
2. Re-run the failed job from the Actions UI, or re-run the workflows with
   **Run workflow → workflow_dispatch on the tag ref**.

A script-only fix that should not change the version is published by deleting
and re-pushing the same tag — but only before anyone has pulled it.
