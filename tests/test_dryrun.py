"""Modo dry-run: datos SINTÉTICOS que recorren toda la tubería sin red ni API key."""

from mvpup.consolidation import Quadrant, build_matrix, structural_findings
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.dryrun import dry_run_responses, synthetic_dimension_output, synthetic_ligera_output
from mvpup.intake import Intake
from mvpup.orchestrator import LIGERA_TASK_KEY, run_pass
from mvpup.parsing import parse_agent_output, parse_grouped_output, parse_ligera_output
from mvpup.runners import FakeRunner
from mvpup.selection import build_plan


def intake(**kw):
    base = dict(product="Producto Sintético", stage=Stage.MVP, objective=Objective.INGRESOS)
    base.update(kw)
    return Intake(**base)


def test_every_dimension_has_a_valid_synthetic_output():
    for dim in D:
        result = parse_agent_output(synthetic_dimension_output(dim))
        assert 0 <= result.score <= 10
        assert len(result.findings) >= 3 and result.warnings == []
        assert all("[sintético]" in f.evidence for f in result.findings)


def test_synthetic_ligera_output_is_valid():
    result = parse_ligera_output(synthetic_ligera_output())
    assert len(result.resume_tasks) == 3 and len(result.findings) >= 3


def test_responses_cover_every_task_of_the_plan_including_grouped_agents():
    plan = build_plan(intake())
    responses = dry_run_responses(plan, Mode.EXPRESS)
    assert set(responses) == {t.key for t in plan.tasks}
    grouped = next(t for t in plan.tasks if len(t.dimensions) == 2)
    parsed = parse_grouped_output(responses[grouped.key], grouped.dimensions)
    assert set(parsed) == set(grouped.dimensions)


def test_ligera_responses_use_the_ligera_key():
    plan = build_plan(intake(mode=Mode.LIGERA))
    assert set(dry_run_responses(plan, Mode.LIGERA)) == {LIGERA_TASK_KEY}


def test_synthetic_pass_populates_all_four_quadrants_and_a_structural_finding():
    it = intake()
    plan = build_plan(it)
    result = run_pass(it, FakeRunner(dry_run_responses(plan, it.mode)), plan=plan)
    assert result.unevaluated == () and set(result.results) == set(plan.selected)
    matrix = build_matrix(result.results, it.objective)
    assert all(matrix[q] for q in Quadrant)
    assert structural_findings(result.results)
