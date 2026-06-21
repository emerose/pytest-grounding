# Releasing

Releases publish to [PyPI](https://pypi.org/project/pytest-grounding/) automatically when a
GitHub Release is published, via the [`release.yml`](.github/workflows/release.yml) workflow.
Publishing uses **PyPI Trusted Publishing (OIDC)** — there is no API token stored as a secret.

## One-time setup (before the first release)

**Register the trusted publisher on PyPI.** Because the project doesn't exist on PyPI yet,
use a *pending* publisher: <https://pypi.org/manage/account/publishing/> → add a pending
publisher with:

- **PyPI Project Name:** `pytest-grounding`
- **Owner:** `emerose`
- **Repository name:** `pytest-grounding`
- **Workflow name:** `release.yml`
- **Environment name:** *(leave blank)*

The first successful publish creates the project and converts the pending publisher into a
normal one. No GitHub environment or stored API token is needed.

> Optional hardening: if you later want a manual-approval gate before each publish, create a
> GitHub environment (Settings → Environments) with required reviewers, add `environment: <name>`
> to the `publish` job in `release.yml`, and set the same name in the PyPI publisher config.
> The two must match.

## Cutting a release

1. Bump `version` in `pyproject.toml` and `__version__` in `grounding/__init__.py`.
2. Commit and push to `main`; confirm CI is green.
3. Tag and create a GitHub Release (e.g. `v0.1.0`):

   ```sh
   gh release create v0.1.0 --title v0.1.0 --notes "..."
   ```

4. The `Release` workflow builds the sdist + wheel, runs `twine check`, and publishes to PyPI.

To dry-run the build locally:

```sh
python -m build && twine check dist/*
```
