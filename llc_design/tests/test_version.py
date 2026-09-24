"""Release version consistency checks."""

from importlib.metadata import version

import llc_design


def test_package_version_matches_distribution_metadata() -> None:
    assert llc_design.__version__ == "9.3.1"
    assert llc_design.__version__ == version("power-design-toolkit")
