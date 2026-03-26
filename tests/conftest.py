"""Shared test fixtures."""

import os
import shutil
import subprocess
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

HAS_GDB = shutil.which("gdb") is not None
HAS_CLANGD = shutil.which("clangd") is not None

skip_no_gdb = pytest.mark.skipif(not HAS_GDB, reason="gdb not found")
skip_no_clangd = pytest.mark.skipif(not HAS_CLANGD, reason="clangd not found")


@pytest.fixture(scope="session")
def sample_executable():
    """Compile sample.cpp and return path to executable."""
    src = os.path.join(FIXTURES_DIR, "sample.cpp")
    out = os.path.join(FIXTURES_DIR, "sample")
    subprocess.run(
        ["g++", "-g", "-O0", "-std=c++17", "-o", out, src],
        check=True,
    )
    yield out
    if os.path.exists(out):
        os.remove(out)


@pytest.fixture(scope="session")
def segfault_executable():
    """Compile segfault.cpp and return path to executable."""
    src = os.path.join(FIXTURES_DIR, "segfault.cpp")
    out = os.path.join(FIXTURES_DIR, "segfault")
    subprocess.run(
        ["g++", "-g", "-O0", "-std=c++17", "-o", out, src],
        check=True,
    )
    yield out
    if os.path.exists(out):
        os.remove(out)
