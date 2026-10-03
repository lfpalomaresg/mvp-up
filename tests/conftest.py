"""Fixtures compartidas. TODOS los datos son ficticios (sin datos reales)."""

from __future__ import annotations

import pytest

from support import VALID_OUTPUT


@pytest.fixture
def valid_output() -> str:
    return VALID_OUTPUT
