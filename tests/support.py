"""Salidas de agente e informes de ejemplo. TODOS los datos son ficticios."""

import json

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


LIGERA_OUTPUT = """\
## Score orientativo: 4/10
## Qué es y estado real
Prototipo de ejemplo con README y sin código desplegado.
## Hallazgos clave
- [H1] Sin despliegue · Impacto: A · Evidencia: no hay URL en README.md
- [H2] Ficha desalineada · Impacto: M · Evidencia: N/D
- [H3] Sin métricas · Impacto: M · Evidencia: no hay analítica en index.html
- [H4] Sin licencia · Impacto: B · Evidencia: falta LICENSE en la raíz
## Valor potencial
Sirve al objetivo de reducir trabajo manual.
## 3 tareas de reanudación
1. Desplegar el prototipo
2. Actualizar la ficha
3. Definir una métrica
"""


def write_report(base, slug, date, scores, global_score, objective="ingresos"):
    """Escribe un informe JSON mínimo (ficticio) como los que genera `save_report`."""
    folder = base / slug
    folder.mkdir(parents=True, exist_ok=True)
    data = {"schema": 1, "product": slug.replace("-", " ").title(), "slug": slug, "date": date,
            "objective": objective, "global_score": global_score, "scores": scores}
    (folder / f"{date}-informe.json").write_text(json.dumps(data), encoding="utf-8")
