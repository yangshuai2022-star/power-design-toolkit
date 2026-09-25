"""Wait for a frozen GUI self-test and require fresh, versioned evidence.

A windowed Windows executable need not have stdout. Its exit code alone is not
proof that the intended self-test ran, so the child must also write a report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence


def verify_bundle(
    command: Sequence[str], *, expected_version: str,
    expected_taxonomy_sha256: str, timeout_s: float = 300.0,
) -> dict:
    if not command or timeout_s <= 0:
        raise ValueError("command and positive timeout are required")
    with tempfile.TemporaryDirectory(prefix="pdt-bundle-test-") as directory:
        report_path = Path(directory) / "self-test.json"
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   PDT_SELF_TEST_REPORT=str(report_path))
        # Run outside the source tree; do not let the repository mask absent data.
        process = subprocess.run(
            [*command, "--self-test"], cwd=directory, env=env,
            capture_output=True, text=True, errors="replace", timeout=timeout_s,
        )
        for output in (process.stdout, process.stderr):
            if output:
                print(output, end="" if output.endswith("\n") else "\n")
        process.check_returncode()
        if not report_path.is_file():
            raise RuntimeError("packaged self-test report was not produced")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        required = {
            "success": True, "frozen": True, "version": expected_version,
            "platform": sys.platform,
            "workspaces": ["llc", "pfc", "control", "fra"],
            "guided_design": True,
            "brand_taxonomy_sha256": expected_taxonomy_sha256,
        }
        if not isinstance(report, dict) or any(report.get(k) != v for k, v in required.items()):
            raise RuntimeError(f"invalid packaged self-test report: {report!r}")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--taxonomy", type=Path, default=Path("engineering_data/brand_taxonomy.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    expected_sha = hashlib.sha256(args.taxonomy.read_bytes()).hexdigest()
    report = verify_bundle(
        [str(executable)], expected_version=args.version,
        expected_taxonomy_sha256=expected_sha,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    print("Frozen application verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
