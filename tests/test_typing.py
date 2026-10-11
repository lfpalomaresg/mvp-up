"""Puerta de tipos: `mypy --check-untyped-defs src` debe quedar limpio.

Se salta solo si mypy no está instalado (está en el extra `dev`, así que en CI corre).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_mypy_check_untyped_defs_is_clean():
    if shutil.which("mypy") is None:
        try:
            import mypy  # noqa: F401
        except ImportError:
            pytest.skip("mypy no instalado (pip install -e '.[dev]')")
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--check-untyped-defs", "src"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
