from datetime import date

import pytest

from mvpup.compare import compare_with_previous, format_delta
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.parsing import GROUP_SEPARATOR
from mvpup.report import build_report, render_markdown, save_report
from mvpup.runners import FakeRunner
from support import VALID_OUTPUT


def pass_with(tecnica="6/10", objective=Objective.INGRESOS, stage=Stage.MVP, tecnica_text=None):
    intake = Intake(product="Producto Demo", stage=stage, objective=objective)
    tec = VALID_OUTPUT.replace("6/10", tecnica)
    if tecnica_text:
        tec = tec.replace("Sin tests automatizados", tecnica_text)
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    runner = FakeRunner({"tecnica": tec, "producto_ux": VALID_OUTPUT, "comercial+marketing": grouped})
    return run_pass(intake, runner)


def saved(tmp_path, when, **kw):
    report = build_report(pass_with(**kw), today=when, base_dir=tmp_path)
    save_report(report, tmp_path)
    return report


def test_format_delta():
    assert format_delta(5, 7) == "+2"
    assert format_delta(7, 7) == "="
    assert format_delta(7, 5.5) == "🔴 -1,5"
    assert format_delta(None, 7) == "nuevo"
    assert format_delta(7, None) == "—"


def test_second_pass_shows_deltas_and_red_drop(tmp_path):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10")
    report = build_report(pass_with(tecnica="5/10"), today=date(2026, 10, 4), base_dir=tmp_path)
    assert report.deltas[D.TECNICA] == "🔴 -3"
    assert report.deltas[D.COMERCIAL] == "="
    md = render_markdown(report)
    assert "| Técnica | 5/10 | 🔴 -3 | 🟡 |" in md
    assert any("bajó" in line and "Técnica" in line for line in report.evolution)


def test_actions_no_longer_found_are_counted(tmp_path):
    saved(tmp_path, date(2026, 9, 1))
    report = build_report(
        pass_with(tecnica_text="Cobertura de tests insuficiente"), today=date(2026, 10, 4), base_dir=tmp_path
    )
    joined = "\n".join(report.evolution)
    assert "ya no aparecen" in joined
    assert "Sin tests automatizados" in joined


def test_objective_change_marks_deltas_not_comparable_and_recomputes(tmp_path):
    saved(tmp_path, date(2026, 9, 1), objective=Objective.INGRESOS)
    report = build_report(
        pass_with(objective=Objective.VENDIBLE), today=date(2026, 10, 4), base_dir=tmp_path
    )
    joined = "\n".join(report.evolution)
    assert "no comparables directamente" in joined
    assert "recalculado con los pesos nuevos" in joined


def test_old_previous_report_warns(tmp_path):
    saved(tmp_path, date(2026, 1, 1))
    report = build_report(pass_with(), today=date(2026, 10, 4), base_dir=tmp_path)
    assert any("más de 6 meses" in line for line in report.evolution)


def test_stage_change_is_reported(tmp_path):
    saved(tmp_path, date(2026, 9, 1), stage=Stage.MVP)
    report = build_report(pass_with(stage=Stage.PRODUCCION), today=date(2026, 10, 4), base_dir=tmp_path)
    assert any("etapa" in line.lower() for line in report.evolution)


def test_compare_ignores_corrupt_previous_json(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    (folder / "2026-09-01-informe.md").write_text("# informe", encoding="utf-8")
    (folder / "2026-09-01-informe.json").write_text("{no es json", encoding="utf-8")
    report = build_report(pass_with(), today=date(2026, 10, 4), base_dir=tmp_path)
    assert any("ilegible" in line for line in report.evolution)


def test_compare_with_previous_is_pure():
    report = build_report(pass_with(), today=date(2026, 10, 4))
    prev = {"schema": 1, "date": "2026-09-01", "objective": "ingresos", "stage": "mvp",
            "global_score": 6.0, "scores": {"tecnica": 4, "comercial": 6}, "roadmap": []}
    compare_with_previous(report, prev)
    assert report.deltas[D.TECNICA] == "+2"
    assert report.deltas[D.PRODUCTO_UX] == "nuevo"


def test_markdown_only_previous_pass_counts_and_warns(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    (folder / "2026-09-01-informe.md").write_text("# informe antiguo sin JSON", encoding="utf-8")
    report = build_report(pass_with(), today=date(2026, 10, 4), base_dir=tmp_path)
    assert report.pass_number == 2
    assert any("sin JSON gemelo" in line for line in report.evolution)


def test_objective_change_makes_table_deltas_not_comparable(tmp_path):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10", objective=Objective.INGRESOS)
    report = build_report(pass_with(tecnica="6/10", objective=Objective.VENDIBLE),
                          today=date(2026, 10, 4), base_dir=tmp_path)
    assert report.deltas[D.TECNICA] == "n/c (8→6)"
    assert "🔴" not in report.deltas[D.TECNICA]


def test_drop_cause_uses_new_high_impact_findings_with_evidence(tmp_path):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10")
    report = build_report(
        pass_with(tecnica="5/10", tecnica_text="Fuga de memoria en el worker"),
        today=date(2026, 10, 4), base_dir=tmp_path,
    )
    line = next(ln for ln in report.evolution if "bajó" in ln)
    assert "Fuga de memoria en el worker" in line
    assert "Evidencia: no existe carpeta tests/" in line
    assert "nuevo desde la pasada anterior" in line


def test_drop_without_new_findings_does_not_invent_cause(tmp_path):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10")
    report = build_report(pass_with(tecnica="5/10"), today=date(2026, 10, 4), base_dir=tmp_path)
    line = next(ln for ln in report.evolution if "bajó" in ln)
    assert "sin hallazgo nuevo de impacto alto" in line


@pytest.mark.parametrize("prev, today, stale", [
    ("2026-02-01", date(2026, 8, 3), True),   # >6 meses naturales (183 días)
    ("2026-02-01", date(2026, 8, 1), False),  # exactamente 6 meses
    ("2025-08-31", date(2026, 3, 1), True),   # fin de mes: 31-ago + 6m = 28-feb
])
def test_six_calendar_months(prev, today, stale):
    from mvpup.compare import older_than_six_months

    assert older_than_six_months(date.fromisoformat(prev), today) is stale


def test_objective_change_does_not_narrate_drops_as_red(tmp_path):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10", objective=Objective.INGRESOS)
    report = build_report(pass_with(tecnica="6/10", objective=Objective.VENDIBLE),
                          today=date(2026, 10, 4), base_dir=tmp_path)
    joined = "\n".join(report.evolution)
    assert "🔴" not in joined and "bajó" not in joined
    assert "Técnica 8 → 6" in joined


def test_orphan_json_without_markdown_is_not_a_pass(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    (folder / "2026-09-01-informe.json").write_text('{"scores": {}}', encoding="utf-8")
    report = build_report(pass_with(), today=date(2026, 10, 4), base_dir=tmp_path)
    assert report.pass_number == 1
    assert report.evolution == []


@pytest.mark.parametrize("name", ["2026-10-01-informe-backup.md", "notas-informe-borrador.md"])
def test_non_report_markdown_is_not_a_pass(tmp_path, name):
    saved(tmp_path, date(2026, 9, 1), tecnica="8/10")
    (tmp_path / "producto-demo" / name).write_text("# otra cosa", encoding="utf-8")
    report = build_report(pass_with(tecnica="5/10"), today=date(2026, 10, 4), base_dir=tmp_path)
    assert report.pass_number == 2
    assert report.deltas[D.TECNICA] == "🔴 -3"
