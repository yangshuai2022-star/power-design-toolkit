# Release process

Power Design Toolkit publishes **versioned Git tags** and **GitHub Releases** with Windows x64 and macOS Apple Silicon zip artifacts.

There is **one supported publish path**. Do not hand-craft tags that disagree with `pyproject.toml`.

---

## Contract

| Source of truth | Location |
| --- | --- |
| Package / product version | `pyproject.toml` → `[project].version` |
| Runtime version string | `llc_design.__version__` (must match package) |
| Git tag | `v{version}` (example: `9.4.0` → `v9.4.0`) |
| Human history | `CHANGELOG.md` |
| Binary installers | GitHub Release assets from CI |

CI refuses a tagged build when `refs/tags/vX.Y.Z` ≠ `v` + package version.

---

## Mandatory release-scope preflight

A green build of the wrong source tree is not a completed release. Before promoting a release candidate, record the intended feature branches/commit SHAs in the release PR and inspect their real diffs against the current `main`; branch names and commit-message searches alone are insufficient.

1. Pin current `main` and every release-required feature head. Distinguish required work from unrelated/stale branches; do not merge all branches indiscriminately.
2. Verify the candidate actually includes the intended feature changes. After a merge, check ancestry and review the final diff. With squash/cherry-pick history, verify patch/content equivalence instead of assuming ancestry.
3. Run full regression and required simulator/GUI checks on the merged candidate. If the candidate changes, the old green result is not sufficient.
4. Align package/runtime/test/README/CHANGELOG version metadata atomically in the candidate. Preparing metadata on the PR is allowed; tagging/publishing happens only after integration to `main` and CI gates.
5. Confirm the final release tag resolves to the reviewed commit, includes every required feature head, and has the expected version. Verify both platform assets and packaged self-tests before reporting publication complete.

For the V9.4 integration, the release-required original feature head is `ae58161b11c4246e7a81e25b25a9260ec065030d` from `feature/v9.3-guided-smart-control-ui`. PR #22 also carries the release-regression/launcher fixes and version metadata. Published v9.3.0/v9.3.1 tags remain unchanged.

This preflight is a maintained human/agent release requirement; the existing CI does not automatically discover which unrelated branch the user intended to release.

---

## Supported method (preferred)

### 1. Finish the work on a branch and merge to `main`

Include:

- code + tests;
- `CHANGELOG.md` section for the new version;
- README / docs updates that users need for the release;
- matching version bumps in `pyproject.toml` and `llc_design/__init__.py`.

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
2. If the version **changed** and tag `vX.Y.Z` does **not** already exist → create annotated tag `vX.Y.Z` and push it. The releaser must ensure this is a valid forward version change.
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

Never move or retag an already-published `vX.Y.Z` that users may have downloaded. Ship a new version instead.

---

## Explicitly unsupported

- Tagging a commit whose `pyproject.toml` version does not match the tag;
- Publishing binaries from a dirty local tree without CI `--self-test`;
- Treating CI green as hardware-release readiness (see `docs/ENGINEERING_VALIDATION.md`);
- Bumping the version on a feature branch and expecting a public Release (Releases are produced from `main` / tags).

---

## Checklist before release

- [ ] Intended release branches/SHAs identified and their actual diffs reviewed;
- [ ] Release-required feature changes included in the candidate; no required feature is left outside `main` when tagging;
- [ ] Full tests and required simulator/GUI checks green for the merged candidate;
- [ ] `CHANGELOG.md` has the new version section and preserves model limitations;
- [ ] README version badge matches;
- [ ] `llc_design.__version__` matches `pyproject.toml` and version regression;
- [ ] no intentional UNKNOWN / APPROXIMATION claims re-labeled as VERIFIED;
- [ ] final tag/commit identity and both packaged release assets verified.
