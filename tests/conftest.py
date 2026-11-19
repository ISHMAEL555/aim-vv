import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import aim_ctypes  # noqa: E402


@pytest.fixture(scope="session")
def lib():
    return aim_ctypes.load()
