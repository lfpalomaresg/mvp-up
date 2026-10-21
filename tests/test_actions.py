"""Acción por hallazgo: plantilla, parser (fallo cerrado), roadmap/TOP-5 e informes antiguos.

Todos los datos son ficticios.
"""

import json
import re
from datetime import date
from pathlib import Path

import pytest
from support import LIGERA_OUTPUT

from mvpup.cli import main
from mvpup.compare import diff_reports
from mvpup.consolidation import build_matrix
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.parsing import (
    ACTION_MAX_CHARS,
    DimensionResult,
    Finding,
    FormatError,
    Level,
    parse_agent_output,
    parse_ligera_output,
)
from mvpup.prompts import build_task_prompt
from mvpup.report import build_report, render_markdown, save_report, to_json
from mvpup.roadmap import build_roadmap, top_five
from mvpup.runners import FakeRunner
from mvpup.selection import AgentTask

TODAY = date(2026, 10, 12)
DIM_MD = Path(__file__).parents[1] / "skill" / "references" / "dimensiones.md"

OUTPUT = """\
## Score: 5/10 (rúbrica al pie)
## Hallazgos (máx 7, ordenados por impacto)
- [H1] El alta de clientes es manual y depende de un script del operador · Impacto: A · Esfuerzo: B · Evidencia: scripts/alta.py · Acción: Publicar un formulario de alta autoservicio
- [H2] No hay precios públicos · Impacto: A · Esfuerzo: M · Evidencia: web/precios.html vacío · Acción: Publicar la página de precios
## Quick wins (impacto A/M con esfuerzo B)
## Riesgos si no se actúa
## Datos que faltan para evaluar mejor
"""
LEGACY_LINE = "- [H1] El alta de clientes es manual · Impacto: A · Esfuerzo: B · Evidencia: scripts/alta.py"


# --- plantilla -------------------------------------------------------------------------------


def test_prompt_asks_for_a_short_imperative_action_per_finding():
    p = build_task_prompt(AgentTask((D.TECNICA,)), Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS))
    line = next(ln for ln in p.splitlines() if ln.startswith("- [H1]"))
    assert line.endswith("· Acción: <qué hacer: verbo en infinitivo + objeto, máx 15 palabras>")
    assert "no repitas el hallazgo" in p.lower()


def test_prompt_finding_line_is_the_one_in_the_skill_markdown():
    p = build_task_prompt(AgentTask((D.TECNICA,)), Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS))
    line = next(ln for ln in p.splitlines() if ln.startswith("- [H1]"))
    assert line in DIM_MD.read_text(encoding="utf-8").splitlines()


# --- parser ----------------------------------------------------------------------------------


def test_parser_keeps_the_action_of_each_finding():
    findings = parse_agent_output(OUTPUT).findings
    assert [f.action for f in findings] == ["Publicar un formulario de alta autoservicio", "Publicar la página de precios"]
    assert findings[0].text == "El alta de clientes es manual y depende de un script del operador"
    assert findings[0].evidence == "scripts/alta.py"  # la acción no se cuela en la evidencia


def test_evidence_may_contain_middle_dots_before_the_action():
    text = OUTPUT.replace("Evidencia: scripts/alta.py ·", "Evidencia: scripts/alta.py · docs/alta.md ·")
    f = parse_agent_output(text).findings[0]
    assert f.evidence == "scripts/alta.py · docs/alta.md" and f.action.startswith("Publicar un formulario")


@pytest.mark.parametrize("broken, problem", [
    (LEGACY_LINE, "falta la acción"),
    (LEGACY_LINE + " · Acción:", "falta la acción"),
    (LEGACY_LINE + " · Acción: N/D", "falta la acción"),
    (LEGACY_LINE + " · Acción: <qué hacer>", "falta la acción"),
    (LEGACY_LINE + " · Acción: " + "Hacer algo muy largo " * 20, "acción demasiado larga"),
    (LEGACY_LINE + " · Acción: El alta de clientes es manual", "repite el hallazgo"),
])
def test_missing_or_invalid_action_fails_closed(broken, problem):
    text = OUTPUT.replace(next(ln for ln in OUTPUT.splitlines() if ln.startswith("- [H1]")), broken)
    with pytest.raises(FormatError) as exc:
        parse_agent_output(text)
    assert any("H1" in p and problem in p for p in exc.value.problems)


def test_action_length_limit_is_inclusive():
    action = "Publicar " + "x" * (ACTION_MAX_CHARS - len("Publicar "))
    text = OUTPUT.replace("Acción: Publicar un formulario de alta autoservicio", f"Acción: {action}")
    assert parse_agent_output(text).findings[0].action == action


def test_finding_without_evidence_is_still_discarded_not_a_format_error():
    """El descarte por evidencia manda: no se exige acción a lo que no llega al informe."""
    text = OUTPUT.replace("Evidencia: web/precios.html vacío · Acción: Publicar la página de precios", "Evidencia: N/D")
    r = parse_agent_output(text)
    assert [f.id for f in r.findings] == ["H1"] and any("H2" in w for w in r.warnings)


def test_missing_action_triggers_one_retry_and_then_recovers():
    legacy = OUTPUT.replace(" · Acción: Publicar un formulario de alta autoservicio", "")
    runner = FakeRunner({"tecnica": [legacy, OUTPUT], "*": OUTPUT})
    intake = Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS, remove={"producto_ux", "comercial", "marketing"})
    result = run_pass(intake, runner)
    assert result.results[D.TECNICA].findings[0].action
    assert any("falta la acción" in ln for ln in result.log)
    retry_prompt = [p for k, p in runner.calls if k == "tecnica"][1]
    assert "falta la acción" in retry_prompt  # el reintento dice qué faltó


def test_ligera_template_does_not_require_action():
    assert all(f.action == "" for f in parse_ligera_output(LIGERA_OUTPUT).findings)


# --- roadmap, TOP-5 e informe ----------------------------------------------------------------


def _finding(id_, text, action, imp=Level.ALTO, eff=Level.BAJO):
    return Finding(id=id_, text=text, impact=imp, effort=eff, evidence="README.md", action=action)


def _roadmap(*findings):
    results = {D.COMERCIAL: DimensionResult(score=5, findings=list(findings))}
    return build_roadmap(build_matrix(results, Objective.INGRESOS), Objective.INGRESOS)


def test_top_five_leads_with_the_action_and_keeps_the_finding_as_context():
    top = top_five(_roadmap(_finding("H1", "No hay precios públicos", "Publicar la página de precios")))
    assert top == ["Publicar la página de precios (hallazgo: No hay precios públicos) · Comercial · H1"]


def test_top_five_truncates_a_long_finding_used_as_context():
    long_text = "El alta de clientes es manual. " * 20
    top = top_five(_roadmap(_finding("H1", long_text.strip(), "Automatizar el alta")))[0]
    assert top.startswith("Automatizar el alta (hallazgo: El alta de clientes es manual.")
    assert "…)" in top and len(top) < 220


def test_finding_without_action_falls_back_to_its_text():
    """Hallazgos de informes/parsers antiguos (sin acción): se muestra el hallazgo, como antes."""
    top = top_five(_roadmap(_finding("H1", "No hay precios públicos", "")))
    assert top == ["No hay precios públicos · Comercial · H1"]


def _report(tmp_path=None):
    intake = Intake(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS,
                    remove={"producto_ux", "comercial", "marketing"})
    return build_report(run_pass(intake, FakeRunner({"*": OUTPUT})), today=TODAY, base_dir=tmp_path)


def test_report_roadmap_shows_action_with_finding_and_evidence_as_context():
    md = render_markdown(_report())
    section = md.split("## Roadmap de escalado", 1)[1].split("## Evolución", 1)[0]
    lines = section.splitlines()
    i = lines.index("- [ ] Publicar un formulario de alta autoservicio · sube Técnica")
    assert lines[i + 1] == (
        "  - Hallazgo: El alta de clientes es manual y depende de un script del operador "
        "(Técnica · Evidencia: scripts/alta.py)"
    )
    top = md.split("## TOP-5 propuesto para autorización", 1)[1]
    assert "1. Publicar un formulario de alta autoservicio (hallazgo: El alta de clientes" in top


def test_report_json_stores_action_and_finding_separately():
    data = to_json(_report())
    first = data["roadmap"][0]
    assert first["action"] == "Publicar un formulario de alta autoservicio"
    assert first["finding"] == "El alta de clientes es manual y depende de un script del operador"
    assert first["finding_id"] == "H1"
    assert data["findings"][0]["action"] == "Publicar un formulario de alta autoservicio"


# --- compatibilidad con informes antiguos ----------------------------------------------------

# Forma EXACTA del JSON de la primera pasada real (2026-10-12): sin `action` en los hallazgos y
# con el texto del hallazgo como `action` del roadmap. Contenido ficticio.
LEGACY_REPORT = {
    "schema": 1, "product": "Producto Demo", "slug": "producto-demo", "date": "2026-10-12",
    "mode": "express", "stage": "mvp", "objective": "ingresos", "pass_number": 1, "dry_run": False,
    "global_score": 4.7, "scores": {"tecnica": 7, "producto_ux": 5, "comercial": 4, "marketing": 4},
    "not_applicable": [], "unevaluated": [],
    "roadmap": [
        {"horizon": "H1", "dimension": "tecnica", "dimensions": ["tecnica"],
         "action": "El alta de clientes es manual y depende de un script del operador"},
        {"horizon": "H2", "dimension": "comercial", "dimensions": ["comercial"], "action": "No hay cliente de pago"},
    ],
    "findings": [
        {"dimension": "tecnica", "id": "H1", "text": "El alta de clientes es manual y depende de un script del operador",
         "impact": "A", "effort": "B", "evidence": "scripts/alta.py"},
        {"dimension": "comercial", "id": "H1", "text": "No hay cliente de pago", "impact": "A", "effort": "M",
         "evidence": "STATUS.md"},
    ],
    "top": ["El alta de clientes es manual y depende de un script del operador · Técnica · H1"],
    "log": [],
}


def test_legacy_report_still_compares_against_a_new_one():
    """La acción antigua era el texto del hallazgo: si el hallazgo sigue, la acción sigue abierta."""
    diff = diff_reports(LEGACY_REPORT, to_json(_report()))
    assert diff.open == ["El alta de clientes es manual y depende de un script del operador"]
    assert diff.closed == ["No hay cliente de pago"]
    # La acción nueva del MISMO hallazgo no es «nueva»: solo cambió cómo se redacta.
    assert diff.new == ["Publicar la página de precios"]


def test_two_new_reports_match_actions_by_action_or_by_finding():
    previous = to_json(_report())
    current = json.loads(json.dumps(previous))
    current["roadmap"][0]["action"] = "Montar el alta autoservicio"  # misma causa, otra redacción
    diff = diff_reports(previous, current)
    assert diff.new == [] and diff.closed == []
    assert "Publicar un formulario de alta autoservicio" in diff.open


def test_next_pass_evolution_reads_a_legacy_previous_report(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    (folder / "2026-10-01-informe.md").write_text("# informe antiguo\n", encoding="utf-8")
    (folder / "2026-10-01-informe.json").write_text(json.dumps(LEGACY_REPORT), encoding="utf-8")
    md = render_markdown(_report(tmp_path))
    evolution = md.split("## Evolución (solo si hay pasada anterior)", 1)[1].split("## Datos pendientes", 1)[0]
    assert "falló" not in evolution and "ilegible" not in evolution
    assert "1/2" in evolution  # «No hay cliente de pago» ya no aparece; el alta manual sigue abierta
    assert "⏳ sigue abierta: El alta de clientes es manual" in evolution


def test_cli_compare_loads_a_legacy_json_next_to_a_new_report(tmp_path, capsys):
    old = tmp_path / "antiguo.json"
    old.write_text(json.dumps(LEGACY_REPORT), encoding="utf-8")
    new = save_report(_report(), tmp_path)
    assert main(["compare", str(old), str(new)]) == 0
    out = capsys.readouterr().out
    assert "## Acciones que siguen abiertas" in out and "⏳ El alta de clientes es manual" in out
    assert re.search(r"\| Técnica \| 7/10 \| 5/10 \| 🔴 -2 \|", out)


def test_action_rule_in_prompt_is_the_one_in_the_skill_markdown():
    from mvpup.prompts import ACTION_RULE

    p = build_task_prompt(AgentTask((D.TECNICA,)), Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS))
    assert ACTION_RULE in p and f"**Regla de la acción:** {ACTION_RULE}" in DIM_MD.read_text(encoding="utf-8")


# --- Careo ronda 1: lo que la plantilla pide y el parser no exige se AVISA, no se calla ---------


@pytest.mark.parametrize("action, note", [
    ("La página de precios debería estar visible mañana", "no empieza por un verbo en infinitivo"),
    ("Publica la página de precios", "no empieza por un verbo en infinitivo"),
    ("Publicar " + "una cosa " * 8, "17 palabras"),
])
def test_action_off_template_is_kept_but_flagged(action, note):
    """Un reintento cuesta una llamada entera: lo dudoso se acepta y queda a la vista en el log."""
    text = OUTPUT.replace("Acción: Publicar un formulario de alta autoservicio", f"Acción: {action}")
    r = parse_agent_output(text)
    assert r.findings[0].action == action.strip()
    assert any("H1" in n and note in n for n in r.notes)
    assert r.warnings == []  # no es un hallazgo descartado


@pytest.mark.parametrize("action", [
    "Publicar la página de precios", "Reescribir el titular", "Definir el ICP", "Reducirse a un plan",
    "Añadirlo al README", "Oír a tres clientes", "publicar precios", "Ir a ver al gestor",
])
def test_infinitive_actions_raise_no_note(action):
    text = OUTPUT.replace("Acción: Publicar un formulario de alta autoservicio", f"Acción: {action}")
    assert parse_agent_output(text).notes == []


def test_action_notes_reach_the_pass_log_but_not_the_discarded_list():
    odd = OUTPUT.replace("Acción: Publicar la página de precios", "Acción: Publica la página de precios")
    intake = Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS, remove={"producto_ux", "comercial", "marketing"})
    result = run_pass(intake, FakeRunner({"*": odd}))
    assert any("tecnica" in ln and "H2" in ln and "infinitivo" in ln for ln in result.log)
    md = render_markdown(build_report(result, today=TODAY))
    assert "sin prueba" not in md.split("## Datos pendientes", 1)[1].split("## TOP-5", 1)[0]
