# Release Runbook

How to cut and publish a new version of `doclayer` to PyPI.

---

## 1. Versioning Rules (SemVer)

- **Patch (`0.2.1`):** Bug fixes and runbook corrections.
- **Minor (`0.3.0`):** New features, options, or backward-compatible capabilities.
- **Major (`1.0.0`):** Breaking changes or spec structure migrations.

**Source of truth:** [`doclayer/__init__.py`](doclayer/__init__.py) (`__version__`).

---

## 2. Release Steps

### Step 1: Bump version on a branch
```bash
git checkout -b chore/bump-version
```
Update `__version__` in `doclayer/__init__.py`:
```python
__version__ = "0.2.0"
```

Verify tests and contracts pass:
```bash
python -m unittest discover -s tests
python -m doclayer.cli check --debt
```

### Step 2: Merge to `main`
```bash
git commit -am "chore(release): bump version to 0.2.0"
git push -u origin chore/bump-version
```
Merge the PR into `main`.

### Step 3: Publish GitHub Release
1. Go to **GitHub** -> **Releases** -> **Draft a new release**.
2. **Tag:** `v0.2.0` (target: `main`).
3. **Title:** `v0.2.0: <Short Summary>`.
4. Click **Publish release**.

GitHub Actions (`.github/workflows/publish.yml`) automatically builds and publishes the wheel to PyPI.

---

## 3. Verification

Wait ~2 minutes, then verify in a terminal:
```bash
pip install --upgrade doclayer
doclayer --version
```
