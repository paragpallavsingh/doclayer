# Release Process & Versioning Runbook

This document defines the release cadence, versioning contracts, and automated PyPI publishing pipeline for `doclayer`.

---

## 1. Semantic Versioning Specification (SemVer)

`doclayer` strictly adheres to `MAJOR.MINOR.PATCH` ([Semantic Versioning 2.0.0](https://semver.org/)):

* **MAJOR (`X.0.0`):** Incompatible API breaks, structural spec migrations in `.doclayer/*.md`, or removed CLI subcommands.
* **MINOR (`0.X.0`):** New backward-compatible CLI commands, options, invariant types, or analyzer features (e.g. workspace init support).
* **PATCH (`0.0.X`):** Backward-compatible bug fixes, performance tuning, and runbook corrections.

---

## 2. Single Source of Truth

The package version is declared in **exactly one file**:

* **File:** [`doclayer/__init__.py`](doclayer/__init__.py)
* **Variable:** `__version__ = "X.Y.Z"`

[`pyproject.toml`](pyproject.toml) reads `doclayer.__version__` dynamically via `setuptools.dynamic`. Do **not** hardcode a version number into `pyproject.toml`.

---

## 3. One-Time Setup: PyPI Trusted Publishing (OIDC)

We publish via [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OpenID Connect). This eliminates long-lived API tokens or passwords in GitHub secrets.

1. Log into [pypi.org](https://pypi.org/) with package owner credentials.
2. Go to **Manage Project** -> **Settings** -> **Publishing**.
3. Under **Add a publisher**:
   - **Publisher:** GitHub Actions
   - **Owner:** `paragpallavsingh`
   - **Repository:** `doclayer`
   - **Workflow name:** `publish.yml`
   - **Environment name:** *(leave blank or set to `pypi`)*
4. Click **Add publisher**.

---

## 4. Routine Release Procedure (Step-by-Step)

When ready to cut a release at the end of a sprint/cycle:

### Step 1: Bump the version on a branch
```bash
git checkout -b chore/bump-vX.Y.Z
```
Edit [`doclayer/__init__.py`](doclayer/__init__.py):
```python
__version__ = "0.2.0"
```

### Step 2: Validate locally
```bash
python -m unittest discover -s tests
python -m doclayer.cli check --debt
doclayer --version
```

### Step 3: Commit and merge into `main`
```bash
git add doclayer/__init__.py
git commit -m "chore(release): bump version to 0.2.0"
git push -u origin chore/bump-vX.Y.Z
```
Open PR, pass CI, and merge into `main`.

### Step 4: Create a GitHub Release
1. Navigate to **Releases** -> **Draft a new release** on GitHub.
2. Choose a tag: `v0.2.0` (Target: `main`).
3. Release title: `v0.2.0: Workspace-level init and status reporting`.
4. Click **Generate release notes** and review changelog.
5. Click **Publish release**.

---

## 5. Automated CI/CD Publishing

Once the release is published on GitHub, [`.github/workflows/publish.yml`](.github/workflows/publish.yml) runs automatically:

1. Checks out repository at release tag.
2. Builds clean source distribution (`sdist`) and wheel.
3. Authenticates with PyPI via OIDC.
4. Pushes distribution to [pypi.org/project/doclayer](https://pypi.org/project/doclayer/).

Verify installation in a clean environment:
```bash
pip install --upgrade doclayer
doclayer --version
```
