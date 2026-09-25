"""Exercise real child processes so success cannot be inferred from a launch."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pdt_verify_bundle", ROOT / "packaging/verify_bundle.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _child(tmp_path, *, exit_code=0, report=True, delay=0, **overrides):
    payload = {
        "success": True, "version": "9.4.1", "frozen": True, "platform": sys.platform,
        "workspaces": ["llc", "pfc", "control", "fra"],
        "guided_design": True, "brand_taxonomy_sha256": "a" * 64,
    }
    payload.update(overrides)
    script = tmp_path / "child.py"
    script.write_text(
        "import json, os, pathlib, sys, time\n"
        f"time.sleep({delay!r})\n"
        + (f"pathlib.Path(os.environ['PDT_SELF_TEST_REPORT']).write_text({json.dumps(payload)!r}, encoding='utf-8')\n" if report else "")
        + f"sys.exit({exit_code})\n", encoding="utf-8",
    )
    return [sys.executable, str(script)]


def _verify(command, **kwargs):
    return MODULE.verify_bundle(
        command, expected_version="9.4.1", expected_taxonomy_sha256="a" * 64,
        **kwargs,
    )


def test_completed_success_requires_child_report(tmp_path):
    result = _verify(_child(tmp_path, delay=0.05))
    assert result["success"] is True
    assert result["version"] == "9.4.1"


def test_nonzero_exit_rejected_even_with_success_report(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        _verify(_child(tmp_path, exit_code=7))


def test_zero_exit_without_report_is_not_success(tmp_path):
    with pytest.raises(RuntimeError, match="report"):
        _verify(_child(tmp_path, report=False))


def test_hung_child_times_out(tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        _verify(_child(tmp_path, delay=10), timeout_s=0.1)


@pytest.mark.parametrize("overrides", [
    {"success": False}, {"version": "9.4.0"}, {"frozen": False},
    {"workspaces": ["llc"]}, {"guided_design": False},
    {"brand_taxonomy_sha256": "b" * 64}, {"platform": "wrong"},
])
def test_incomplete_or_wrong_bundle_report_is_rejected(tmp_path, overrides):
    with pytest.raises(RuntimeError, match="report"):
        _verify(_child(tmp_path, **overrides))


def test_publish_waits_for_both_platforms_and_stages_draft():
    text = (ROOT / ".github/workflows/build-release.yml").read_text(encoding="utf-8")
    before, publish = text.split("\n  publish:\n", 1)
    build = before.split("\n  build:\n", 1)[1]
    assert "gh release" not in build
    assert "contents: read" in build
    assert "needs: [test, build]" in publish
    assert "always()" not in publish
    assert "--verify-tag --draft" in publish
    assert publish.index("gh release upload") < publish.index("--draft=false --latest")
    assert "uploaded digest mismatch" in publish


def _archive_gate(tmp_path, monkeypatch, *, missing_mac=False, wrong_taxonomy=False, windows_backslash=False):
    import hashlib
    import textwrap
    import zipfile

    taxonomy = b'{"brands": [{"display_name": "TEST"}]}'
    digest = hashlib.sha256(taxonomy).hexdigest()
    (tmp_path / "engineering_data").mkdir()
    (tmp_path / "engineering_data/brand_taxonomy.json").write_bytes(taxonomy)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="9.4.1"\n')
    (tmp_path / "CHANGELOG.md").write_text('# Changelog\n\n## 9.4.1 — test\nFix\n\n## 9.4.0 — test\nFeatures\n')
    (tmp_path / "release").mkdir()
    for runner, platform, name, exe in (
        ("Windows", "win32", "PowerDesignTool-Windows-x64.zip", "PowerDesignTool/PowerDesignTool.exe"),
        ("macOS", "darwin", "PowerDesignTool-macOS-arm64.zip", "PowerDesignTool.app/Contents/MacOS/PowerDesignTool"),
    ):
        if missing_mac and runner == "macOS":
            continue
        proof = {"success": True, "frozen": True, "version": "9.4.1", "platform": platform,
                 "guided_design": True, "workspaces": ["llc", "pfc", "control", "fra"],
                 "brand_taxonomy_sha256": digest}
        (tmp_path / f"release/bundle-proof-{runner}.json").write_text(json.dumps(proof))
        with zipfile.ZipFile(tmp_path / "release" / name, "w") as bundle:
            bundle.writestr(exe.replace("/", "\\") if windows_backslash and runner == "Windows" else exe, b"fixture executable, not a real bundle")
            bundle.writestr("root\\engineering_data\\brand_taxonomy.json" if windows_backslash and runner == "Windows" else "root/engineering_data/brand_taxonomy.json", b"wrong" if wrong_taxonomy else taxonomy)
    workflow = (ROOT / ".github/workflows/build-release.yml").read_text(encoding="utf-8")
    block = workflow.split("- name: Verify both archives and write checksums\n", 1)[1]
    block = block.split("run: |\n", 1)[1].split("\n      - name:", 1)[0]
    script = textwrap.dedent(block).split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.4.1")
    exec(compile(script, "release-archive-gate", "exec"), {})


def test_archive_gate_accepts_both_complete_packages(tmp_path, monkeypatch):
    _archive_gate(tmp_path, monkeypatch)
    assert len((tmp_path / "release/SHA256SUMS.txt").read_text().splitlines()) == 2


def test_archive_gate_rejects_partial_release(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        _archive_gate(tmp_path, monkeypatch, missing_mac=True)


def test_archive_gate_rejects_wrong_bundled_data(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="taxonomy"):
        _archive_gate(tmp_path, monkeypatch, wrong_taxonomy=True)


def test_archive_gate_handles_windows_zip_separators(tmp_path, monkeypatch):
    _archive_gate(tmp_path, monkeypatch, windows_backslash=True)
    assert len((tmp_path / "release/SHA256SUMS.txt").read_text().splitlines()) == 2
