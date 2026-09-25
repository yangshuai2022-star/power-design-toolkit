# Release process

Power Design Toolkit publishes versioned tags and complete GitHub Releases containing both Windows x64 and macOS Apple Silicon packages. Version changes reach `main` only through a reviewed candidate. Existing published tags are never moved.

## Version and source contract

| Item | Authority |
| --- | --- |
| Product version | `pyproject.toml` `[project].version` |
| Runtime version | `llc_design.__version__`, identical to product version |
| Regression version | `llc_design/tests/test_version.py` |
| Tag | `v{version}` |
| Release content | Reviewed source tree, `CHANGELOG.md` and both verified packages |

## Mandatory release-scope preflight

A green build of the wrong source tree is not a completed release.

1. Pin current `main` and release-required feature heads. Inspect actual diffs; do not guess from branch names or merge unrelated branches indiscriminately.
2. Confirm the candidate contains all intended functionality. Verify ancestry after merge, or patch/content equivalence after squash/cherry-pick.
3. Run full regression and required simulator/GUI checks for that candidate. A changed candidate requires new evidence.
4. Align package/runtime/test/README/CHANGELOG versions in the candidate, before tagging.
5. Verify the final tag resolves to the reviewed merged commit and that both release assets belong to that run.

For V9.4, original required feature head `ae58161b11c4246e7a81e25b25a9260ec065030d` was integrated through PR #22. PR #23 fixes packaging and release verification without changing power/control algorithms. Published v9.3.x and v9.4.0 tags remain unchanged. v9.4.0 is an incomplete release superseded by the 9.4.1 correction, not a tag to overwrite.

This preflight is a maintained human/agent requirement; CI cannot infer which feature branch the user intended to release.

## Supported publish path

Workflow: [build-release.yml](../.github/workflows/build-release.yml).

```text
Reviewed PR with synchronized version metadata
  -> full PR tests + required real-ngspice checks
  -> merge to main
  -> full main regression
  -> annotated vX.Y.Z tag and tag workflow dispatch
  -> tag regression
  -> Windows and macOS platform regression + PyInstaller
  -> frozen executable verification on both platforms
  -> archive/resource/checksum verification
  -> upload BOTH packages and evidence to a DRAFT release
  -> verify remote asset names, sizes and SHA-256 digests
  -> publish complete release
```

`build` matrix jobs have read-only repository permissions and cannot publish a release. The single `publish` job depends on successful `test` and the complete `build` matrix. A failed or skipped platform blocks publication.

## Frozen executable verification

`packaging/verify_bundle.py` starts the actual executable using `subprocess.run`, waits for completion with a timeout, and requires a zero exit code plus a freshly created JSON self-test report. It runs outside the repository working directory, so source-tree data cannot hide missing bundled resources.

The report must confirm the expected runtime version, frozen-process status, platform, construction/show/hide of all four workspaces, Guided System Design construction, and the SHA-256 of the bundled brand taxonomy. The checksum must match the checked-out release source. The child only writes success evidence after completing the tests.

Do not rely on PowerShell's launch expression or a pre-existing `$LASTEXITCODE` to validate a windowed EXE. Do not replace missing data with defaults or disable the self-test to get a green build.

Shared `engineering_data` is explicitly included via PyInstaller `--add-data`. The macOS ZIP retains the outer `.app` directory. Before publication, both archives are checked for CRC errors, executable paths and the actual taxonomy bytes.

## Required public assets

- `PowerDesignTool-Windows-x64.zip`
- `PowerDesignTool-macOS-arm64.zip`
- `bundle-proof-Windows.json`
- `bundle-proof-macOS.json`
- `SHA256SUMS.txt`

Publication starts in draft mode. Upload errors leave a draft rather than a partial public release. Existing published releases are not overwritten by reruns. After the corrected v9.4.1 release is published, the incomplete v9.4.0 entry is marked prerelease/superseded; its tag and assets are retained for history.

## Recovery

For a failed build before publication, correct source through a reviewed patch and use a new version if the old tag was already public. Re-running an existing tag is appropriate only when the checked-out source does not need modification.

```bash
gh workflow run build-release.yml --ref vX.Y.Z
```

A same-tag retry may replace assets in an existing draft. It must not overwrite an already public release or bypass missing-platform/resource/digest gates. Do not publish a release manually with just one platform to work around failed CI.

## Engineering boundary

Passing regression, frozen GUI checks and simulator checks establishes software evidence, not hardware validation. Keep model limitations and UNKNOWN / APPROXIMATION / PARTIAL classifications visible. See [Engineering validation policy](ENGINEERING_VALIDATION.md).
