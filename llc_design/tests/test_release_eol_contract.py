"""Publication-only LF/CRLF equivalence must retain raw evidence integrity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import textwrap
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _script(text, heading):
    block = text.split(f'- name: {heading}\n', 1)[1]
    block = block.split('run: |\n', 1)[1].split('\n      - name:', 1)[0]
    return textwrap.dedent(block).split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


def _gate():
    recovery = (ROOT / '.github/workflows/complete-v942-release.yml').read_text(encoding='utf-8')
    namespace = {'__name__': 'recovery_contract_test'}
    exec(compile(_script(recovery, 'Verify exact v9.4.2 assets and EOL contract'), 'recovery', 'exec'), namespace)
    original = _script((ROOT / '.github/workflows/build-release.yml').read_text(encoding='utf-8'),
                       'Verify both archives and write checksums')
    return original, namespace['rewrite_gate']


def _fixture(tmp_path, monkeypatch, *, crlf, defect=None):
    data = b'{\n  "brands": [{"display_name": "TEST"}]\n}\n'
    (tmp_path / 'engineering_data').mkdir()
    (tmp_path / 'engineering_data/brand_taxonomy.json').write_bytes(data)
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion="9.4.2"\n', encoding='utf-8')
    (tmp_path / 'CHANGELOG.md').write_text('# Changelog\n\n## 9.4.2 — test\nFix\n', encoding='utf-8')
    (tmp_path / 'release').mkdir()
    for runner, platform, name, exe in (
        ('Windows', 'win32', 'PowerDesignTool-Windows-x64.zip', 'PowerDesignTool/PowerDesignTool.exe'),
        ('macOS', 'darwin', 'PowerDesignTool-macOS-arm64.zip', 'PowerDesignTool.app/Contents/MacOS/PowerDesignTool'),
    ):
        raw = data.replace(b'\n', b'\r\n') if crlf and runner == 'Windows' else data
        if defect == 'changed-content-with-matching-proof' and runner == 'Windows':
            raw = raw.replace(b'TEST', b'ALTERED')
        sha = hashlib.sha256(raw).hexdigest()
        if defect == 'wrong-raw-proof' and runner == 'Windows':
            sha = hashlib.sha256(data).hexdigest()
        proof = dict(success=True, frozen=True, version='9.4.2', platform=platform,
                     workspaces=['llc', 'pfc', 'control', 'fra'], guided_design=True,
                     brand_taxonomy_sha256=sha)
        (tmp_path / f'release/bundle-proof-{runner}.json').write_text(json.dumps(proof), encoding='utf-8')
        with zipfile.ZipFile(tmp_path / 'release' / name, 'w') as z:
            z.writestr(exe, b'fixture, not a platform executable')
            z.writestr('root/engineering_data/brand_taxonomy.json', raw)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('GITHUB_REF_NAME', 'v9.4.2')


@pytest.mark.parametrize('crlf', [False, True])
def test_publication_accepts_only_source_lf_or_crlf(tmp_path, monkeypatch, crlf):
    original, rewrite = _gate()
    _fixture(tmp_path, monkeypatch, crlf=crlf)
    if crlf:
        with pytest.raises(AssertionError):
            exec(compile(original, 'original-publisher', 'exec'), {})
    exec(compile(rewrite(original), 'fixed-publisher', 'exec'), {})
    assert len((tmp_path / 'release/SHA256SUMS.txt').read_text().splitlines()) == 2


@pytest.mark.parametrize('defect', ['changed-content-with-matching-proof', 'wrong-raw-proof'])
def test_publication_keeps_source_and_raw_proof_checks(tmp_path, monkeypatch, defect):
    original, rewrite = _gate()
    _fixture(tmp_path, monkeypatch, crlf=True, defect=defect)
    with pytest.raises(AssertionError):
        exec(compile(rewrite(original), 'fixed-publisher', 'exec'), {})


def test_recovery_refuses_unexpected_tagged_publisher():
    _, rewrite = _gate()
    with pytest.raises(AssertionError, match='contract'):
        rewrite('print("not the reviewed publisher")')


def test_future_checkouts_pin_taxonomy_lf():
    text = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    assert '/engineering_data/brand_taxonomy.json text eol=lf' in text.splitlines()


def test_recovery_requires_original_successful_jobs_and_exact_assets():
    text = (ROOT / '.github/workflows/complete-v942-release.yml').read_text(encoding='utf-8')
    assert "github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in text
    for value in ('36120489780', '108024571430', '108027671777', '108027671853',
                  'e8751d37ceb975ae0e8e13b374773e419de6643b', 'len(files) == 5',
                  'refusing to overwrite public release'):
        assert value in text


def test_draft_asset_verification_resolves_numeric_release_id():
    text = (ROOT / '.github/workflows/complete-v942-release.yml').read_text(encoding='utf-8')
    stage = text.split('- name: Stage all five assets and publish after remote digest verification', 1)[1]
    stage = stage.split('- name: Mark incomplete', 1)[0]
    assert '--json databaseId --jq .databaseId' in stage
    assert 'releases/$release_id' in stage
    assert 'releases/tags/$tag' not in stage
    assert stage.index('releases/$release_id') < stage.index('--draft=false')
    assert 'assets[name]["digest"]' in stage
    assert 'refusing to overwrite public release' in stage
