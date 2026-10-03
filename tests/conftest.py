"""Fixtures compartidas. TODOS los datos son ficticios (sin datos reales)."""

from __future__ import annotations

import pytest

VALID_OUTPUT = """\
## Score: 6/10 (rúbrica al pie)
## Hallazgos (máx 7, ordenados por impacto)
- [H1] Sin tests automatizados · Impacto: A · Esfuerzo: B · Evidencia: no existe carpeta tests/
- [H2] Dependencias sin fijar · Impacto: M · Esfuerzo: B · Evidencia: requirements.txt sin versiones
- [H3] Arquitectura monolítica · Impacto: M · Esfuerzo: A · Evidencia: app.py de 2.000 líneas
## Quick wins (impacto A/M con esfuerzo B)
- Añadir pytest con un test de humo
## Riesgos si no se actúa
- Regresiones silenciosas en cada despliegue
## Datos que faltan para evaluar mejor
- Volumen real de usuarios
"""


@pytest.fixture
def valid_output() -> str:
    return VALID_OUTPUT
