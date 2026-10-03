import re
from pathlib import Path

import pytest

from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.parsing import parse_agent_output, parse_ligera_output
from mvpup.prompts import DIMENSION_BLOCKS, GROUP_SEPARATOR, build_task_prompt
from mvpup.selection import AgentTask, build_plan

DIM_MD = Path(__file__).parents[1] / "skill" / "references" / "dimensiones.md"
MD_NUMBER = {D.TECNICA: 1, D.SEGURIDAD: 2, D.LEGAL: 3, D.PRODUCTO_UX: 4, D.COMERCIAL: 5,
             D.MARKETING: 6, D.MERCADO: 7, D.ECONOMICA: 8, D.OPERATIVA: 9, D.DATOS: 10}


def intake(**kw):
    base = dict(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS,
                repo_path="/tmp/demo", context="SaaS ficticio de ejemplo")
    base.update(kw)
    return Intake(**base)


@pytest.mark.parametrize("dim", list(D))
def test_blocks_are_verbatim_copies_of_skill_markdown(dim):
    md = DIM_MD.read_text(encoding="utf-8")
    section = re.search(rf"^## {MD_NUMBER[dim]} · .*?\n(.*?)(?=^---|^## )", md, re.S | re.M)
    assert DIMENSION_BLOCKS[dim] == section.group(1).strip()


def test_single_dimension_prompt_contains_context_rules_and_format():
    p = build_task_prompt(AgentTask((D.TECNICA,)), intake())
    assert "Producto Demo" in p and "/tmp/demo" in p and "no desplegado" in p
    assert "NO modifiques archivos" in p
    assert "## Score: X/10 (rúbrica al pie)" in p
    assert "## Datos que faltan para evaluar mejor" in p
    assert GROUP_SEPARATOR not in p


def test_grouped_prompt_has_one_separator_per_dimension():
    p = build_task_prompt(AgentTask((D.COMERCIAL, D.MARKETING)), intake())
    assert p.count(GROUP_SEPARATOR) == 2
    assert f"{GROUP_SEPARATOR}comercial" in p and f"{GROUP_SEPARATOR}marketing" in p


def test_more_than_two_dimensions_rejected():
    with pytest.raises(ValueError):
        build_task_prompt(AgentTask((D.LEGAL, D.OPERATIVA, D.DATOS)), intake())


def test_service_hint_added_without_software():
    p = build_task_prompt(AgentTask((D.LEGAL,)), intake(has_software=False))
    assert "Producto sin software" in p
    assert "Producto sin software" not in build_task_prompt(AgentTask((D.LEGAL,)), intake())


def _fill(block: str, score: str) -> str:
    return (block.replace("X/10", score)
            .replace("<hallazgo>", "Algo").replace("A/M/B · Esfuerzo: A/M/B", "A · Esfuerzo: B")
            .replace("<archivo/dato concreto>", "README.md"))


def test_grouped_prompt_contract_round_trips_through_parser():
    from mvpup.parsing import parse_grouped_output

    dims = (D.COMERCIAL, D.MARKETING)
    p = build_task_prompt(AgentTask(dims), intake())
    body = p[p.index(GROUP_SEPARATOR):p.index("Rúbrica")].strip()
    first, second = body.split(GROUP_SEPARATOR)[1:]
    filled = GROUP_SEPARATOR + _fill(first, "4/10") + "\n" + GROUP_SEPARATOR + _fill(second, "8/10")
    results = parse_grouped_output(filled, dims)
    assert results[D.COMERCIAL].score == 4 and results[D.MARKETING].score == 8


def test_ligera_prompt_includes_ficha_and_wip_context():
    p = build_task_prompt(
        AgentTask(tuple(D)),
        intake(mode=Mode.LIGERA, ficha_path="fichas/demo.md", wip_context="carril A activo"),
    )
    assert "fichas/demo.md" in p and "carril A activo" in p


def test_template_shown_in_prompt_is_parseable_when_filled():
    """El formato que pedimos debe ser el mismo que el validador acepta."""
    p = build_task_prompt(AgentTask((D.TECNICA,)), intake())
    block = p[p.index("## Score:"):p.index("Rúbrica")].strip()
    filled = _fill(block, "5/10")
    assert parse_agent_output(filled).score == 5


def test_ligera_prompt_template_is_parseable_when_filled():
    plan = build_plan(intake(mode=Mode.LIGERA))
    p = build_task_prompt(plan.tasks[0], intake(mode=Mode.LIGERA))
    block = p[p.index("## Score orientativo"):].strip()
    finding = "- [H1] <hallazgo> · Impacto: A/M/B · Evidencia: <archivo/dato concreto>"
    three = "\n".join(f"- [H{i}] Algo {i} · Impacto: M · Evidencia: f{i}.md" for i in (1, 2, 3))
    filled = block.replace("X/10", "3/10").replace(finding, three).replace("<tarea>", "Hacer algo")
    assert parse_ligera_output(filled).score == 3
