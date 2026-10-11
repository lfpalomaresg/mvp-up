"""Robustez del parser ante salidas sucias o parciales de los agentes.

Regla: fallo CERRADO con mensaje claro. Nada se descarta en silencio y una
dimensión nunca llega al informe con menos de lo que el agente dijo.
"""

import pytest

from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.parsing import GROUP_SEPARATOR, FormatError, parse_agent_output, parse_grouped_output
from mvpup.runners import FakeRunner
from support import VALID_OUTPUT

H2_LINE = "- [H2] Dependencias sin fijar · Impacto: M · Esfuerzo: B · Evidencia: requirements.txt sin versiones"


# --- texto antes/después, envoltorios y codificaciones: se tolera sin perder nada ---

@pytest.mark.parametrize("wrap", [
    lambda t: "Claro, aquí tienes el análisis:\n\n" + t,
    lambda t: t + "\nEspero que te sirva. Avísame si quieres más detalle.\n",
    lambda t: "```markdown\n" + t + "```\n",
    lambda t: t.replace("\n", "\r\n"),
    lambda t: "﻿" + t,
    lambda t: "<analysis>\n" + t + "</analysis>",
])
def test_noise_around_the_template_is_tolerated(wrap):
    r = parse_agent_output(wrap(VALID_OUTPUT))
    assert r.score == 6 and [f.id for f in r.findings] == ["H1", "H2", "H3"]
    assert r.missing_data == ["Volumen real de usuarios"]


def test_prose_before_the_first_header_is_not_a_finding():
    text = "- [H9] Esto es un borrador previo · Impacto: A · Esfuerzo: B · Evidencia: x\n" + VALID_OUTPUT
    assert [f.id for f in parse_agent_output(text).findings] == ["H1", "H2", "H3"]


# --- campos ausentes / salida parcial (análogo a un JSON truncado) ---

def test_truncated_output_names_every_missing_header():
    cut = VALID_OUTPUT.split("## Quick wins")[0]
    with pytest.raises(FormatError) as exc:
        parse_agent_output(cut)
    joined = " ".join(exc.value.problems)
    assert "Quick wins" in joined and "Riesgos" in joined and "Datos que faltan" in joined


def test_empty_output_fails_closed_with_all_headers_listed():
    with pytest.raises(FormatError) as exc:
        parse_agent_output("   \n")
    assert len(exc.value.problems) == 5


@pytest.mark.parametrize("line", [
    "2. [H2] Dependencias sin fijar · Impacto: M · Esfuerzo: B · Evidencia: requirements.txt",
    "- **[H2]** Dependencias sin fijar · Impacto: M · Esfuerzo: B · Evidencia: requirements.txt",
    "- [H2] Dependencias sin fijar · Impacto: M · Evidencia: requirements.txt",
    "- [H2] Dependencias sin fijar · Impacto: Crítico · Esfuerzo: B · Evidencia: requirements.txt",
    "- [H2] Dependencias sin fijar (Impacto M, Esfuerzo B, evidencia requirements.txt)",
])
def test_any_unreadable_finding_line_is_a_format_error_not_a_silent_drop(line):
    with pytest.raises(FormatError, match="ilegible"):
        parse_agent_output(VALID_OUTPUT.replace(H2_LINE, line))


def test_findings_without_any_evidence_fail_closed_instead_of_an_empty_dimension():
    text = VALID_OUTPUT
    for ev in ("no existe carpeta tests/", "requirements.txt sin versiones", "app.py de 2.000 líneas"):
        text = text.replace(f"Evidencia: {ev}", "Evidencia: N/D")
    with pytest.raises(FormatError, match="sin evidencia"):
        parse_agent_output(text)


# --- scores fuera de 0-10 o ilegibles: mensaje que dice qué se encontró ---

@pytest.mark.parametrize("bad, fragment", [
    ("## Score: 11/10 (rúbrica al pie)", "fuera de rango"),
    ("## Score: -2/10 (rúbrica al pie)", "fuera de rango"),
    ("## Score: 10,5/10", "fuera de rango"),
    ("## Score: ?/10 (rúbrica al pie)", "## Score: ?/10"),
    ("## Score: 7/5", "## Score: 7/5"),
    ("## Score: alto", "## Score: alto"),
    ("## Puntuación: 7/10", "Score"),
])
def test_bad_score_messages_are_explicit(bad, fragment):
    with pytest.raises(FormatError) as exc:
        parse_agent_output(VALID_OUTPUT.replace("## Score: 6/10 (rúbrica al pie)", bad))
    assert any(fragment in p for p in exc.value.problems), exc.value.problems


def test_malformed_header_message_quotes_the_near_miss():
    text = VALID_OUTPUT.replace("## Riesgos si no se actúa", "## Riesgos si no actúas")
    with pytest.raises(FormatError) as exc:
        parse_agent_output(text)
    assert any("## Riesgos si no actúas" in p and "Riesgos si no se actúa" in p for p in exc.value.problems)


# --- agrupado: separador en nivel equivocado ---

def test_grouped_output_with_h2_separators_explains_both_missing_blocks():
    text = f"## Dimensión: comercial\n{VALID_OUTPUT}\n## Dimensión: marketing\n{VALID_OUTPUT}"
    with pytest.raises(FormatError) as exc:
        parse_grouped_output(text, (D.COMERCIAL, D.MARKETING))
    joined = " ".join(exc.value.problems)
    assert "comercial" in joined and "marketing" in joined and GROUP_SEPARATOR.strip() in joined


# --- orquestador: respuestas no textuales y avisos visibles ---

def intake(**kw):
    base = dict(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    base.update(kw)
    return Intake(**base)


def grouped_valid():
    return "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))


def test_non_text_agent_response_is_a_logged_failure_not_a_crash():
    runner = FakeRunner({"tecnica": lambda p: None, "producto_ux": lambda p: {"score": 6},
                         "comercial+marketing": grouped_valid()})
    result = run_pass(intake(), runner)
    assert set(result.unevaluated) == {D.TECNICA, D.PRODUCTO_UX}
    assert any("tecnica" in ln and "no devolvió texto" in ln for ln in result.log)


def test_discarded_findings_are_visible_in_log_and_report():
    from datetime import date

    from mvpup.report import build_report, render_markdown

    tec = VALID_OUTPUT.replace("Evidencia: requirements.txt sin versiones", "Evidencia: N/D")
    runner = FakeRunner({"tecnica": tec, "producto_ux": VALID_OUTPUT, "comercial+marketing": grouped_valid()})
    result = run_pass(intake(), runner)
    assert any("tecnica" in ln and "H2" in ln and "sin evidencia" in ln for ln in result.log)
    md = render_markdown(build_report(result, today=date(2026, 10, 4)))
    assert "H2" in md and "sin evidencia" in md
