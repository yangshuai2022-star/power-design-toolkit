# Release process

Power Design Toolkit publishes **versioned Git tags** and **GitHub Releases** with Windows x64 and macOS Apple Silicon zip artifacts.

There is **one supported publish path**. Do not hand-craft tags that disagree with `pyproject.toml`.

---

## Contract

| Source of truth | Location |
| --- | --- |
| Package / product version | `pyproject.toml` → `[project].version` |
| Runtime version string | `llc_design.__version__` (must match package) |
| Git tag | `v{version}` (example: `9.3.1` → `v9.3.1`) |
| Human history | `CHANGELOG.md` |
| Binary installers | GitHub Release assets from CI |

CI refuses a tagged build when `refs/tags/vX.Y.Z` ≠ `v` + package version.

---

## Supported method (preferred)

### 1. Finish the work on a branch and merge to `main`

Include:

- code + tests;
- `CHANGELOG.md` section for the new version;
- README / docs updates that users need for the release;
- matching version bumps in `pyproject.toml` and `llc_design/__version__`.

### 2. Bump the version only when ready to publish

```text
pyproject.toml          version = "X.Y.Z"
llc_design/__init__.py  __version__ = "X.Y.Z"
```

Update the README version badge to the same `X.Y.Z`.

### 3. Push `main`

```bash
git checkout main
git pull
git push origin main
```

### 4. What CI does automatically

Workflow: [`.github/workflows/build-release.yml`](../.github/workflows/build-release.yml)

On **push to `main`** after tests pass:

1. Compare previous vs current `pyproject.toml` version.
2. If the version **increased** and tag `vX.Y.Z` does **not** already exist → create annotated tag `vX.Y.Z` and push it.
3. Dispatch the same workflow on that tag.
4. On the **tag** run: build PyInstaller packages (Windows + macOS), run packaged `--self-test`, upload zips, publish / update the **GitHub Release**.

On **tag push** / **workflow_dispatch** at a tag: packaging + Release only (after tests).

### 5. Verify the Release page

Open:

https://github.com/yangshuai2022-star/power-design-toolkit/releases

Expect:

- `PowerDesignTool-Windows-x64.zip`
- `PowerDesignTool-macOS-arm64.zip`
- auto-generated notes plus the CI release body (install + gate text)

---

## Manual recovery (only when automation could not finish)

Use when the tag exists but the GitHub Release or assets are missing, or `gh` / Actions need a re-run.

```bash
# Re-run packaging from an existing tag
gh workflow run build-release.yml --ref vX.Y.Z

# Or create / update the Release metadata without rebuilding (assets still need the workflow)
gh release create vX.Y.Z \
  --title "Power Design Toolkit vX.Y.Z" \
  --notes-file CHANGELOG.md \
  --verify-tag
```

Never move or retag an already-published `vX.Y.Z` that users may have downloaded. Ship `X.Y.(Z+1)` instead.

---

## Explicitly unsupported

- Tagging a commit whose `pyproject.toml` version does not match the tag;
- Publishing binaries from a dirty local tree without CI `--self-test`;
- Treating CI green as hardware-release readiness (see `docs/ENGINEERING_VALIDATION.md`);
- Bumping the version on a feature branch and expecting a public Release (Releases are produced from `main` / tags).

---

## Checklist before bumping

- [ ] `pytest` green locally (or known CI-equivalent);
- [ ] `CHANGELOG.md` has the new version section;
- [ ] README version badge matches;
- [ ] `llc_design.__version__` matches `pyproject.toml`;
- [ ] no intentional UNKNOWN / APPROXIMATION claims re-labeled as VERIFIED.
