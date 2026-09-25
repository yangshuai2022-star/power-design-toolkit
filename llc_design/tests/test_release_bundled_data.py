"""Regression for the v9.4.0 packaged-startup missing-taxonomy failure.

The workflow contract catches omission before expensive packaging. The real
Windows/macOS executable self-tests remain the final packaging authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

import power_control_tools.part_validation as part_validation


ROOT = Path(__file__).resolve().parents[2]


def test_desktop_packaging_collects_shared_engineering_data():
    workflow = (ROOT / ".github/workflows/build-release.yml").read_text(encoding="utf-8")
    assert '--add-data "engineering_data:engineering_data"' in workflow
    data = json.loads((ROOT / "engineering_data/brand_taxonomy.json").read_text(encoding="utf-8"))
    assert isinstance(data.get("brands"), list) and data["brands"]
    assert all(item.get("display_name") for item in data["brands"])


def test_taxonomy_loads_relative_to_bundle_not_working_directory(tmp_path, monkeypatch):
    expected = part_validation.load_brand_taxonomy()
    bundle = tmp_path / "bundle"
    module = bundle / "power_control_tools/part_validation.py"
    module.parent.mkdir(parents=True)
    module.write_text("# Simulated bundled module location.\n", encoding="utf-8")
    data = bundle / "engineering_data/brand_taxonomy.json"
    data.parent.mkdir()
    shutil.copyfile(ROOT / "engineering_data/brand_taxonomy.json", data)
    cwd = tmp_path / "unrelated-working-directory"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(part_validation, "__file__", str(module))
    assert part_validation.load_brand_taxonomy() == expected
    assert part_validation.brand_display_names() == tuple(
        str(item["display_name"]) for item in expected["brands"]
    )


def test_missing_bundled_taxonomy_is_not_silently_replaced(tmp_path, monkeypatch):
    module = tmp_path / "bundle/power_control_tools/part_validation.py"
    module.parent.mkdir(parents=True)
    monkeypatch.setattr(part_validation, "__file__", str(module))
    with pytest.raises(FileNotFoundError):
        part_validation.load_brand_taxonomy()
