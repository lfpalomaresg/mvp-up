"""Fixtures compartidas. TODOS los datos son ficticios (sin datos reales)."""

from __future__ import annotations

import pytest

from support import VALID_OUTPUT, write_report


@pytest.fixture
def valid_output() -> str:
    return VALID_OUTPUT


@pytest.fixture
def cartera(tmp_path):
    """Carpeta de informes ficticia con 3 productos (app-uno tiene 2 pasadas)."""
    write_report(tmp_path, "app-uno", "2026-09-01", {"tecnica": 3, "comercial": 3}, 3.0)
    write_report(tmp_path, "app-uno", "2026-10-01", {"tecnica": 8, "comercial": 3, "datos": None}, 4.7)
    write_report(tmp_path, "app-dos", "2026-10-02", {"tecnica": 7, "comercial": 4, "datos": None}, 5.0)
    write_report(tmp_path, "app-tres", "2026-10-03", {"tecnica": 6, "comercial": 2, "datos": 3}, 3.3)
    return tmp_path
