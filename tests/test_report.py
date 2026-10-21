import json
import re
from datetime import date
from pathlib import Path

import pytest
from support import LIGERA_OUTPUT, VALID_OUTPUT

from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.parsing import GROUP_SEPARATOR
from mvpup.report import build_report, render_markdown, report_dir, save_report, slugify
from mvpup.report import to_json as report_to_json
from mvpup.runners import FakeRunner

TEMPLATE = Path(__file__).parents[1] / "skill" / "references" / "plantilla-informe.md"
TODAY = date(2026, 10, 4)


def express_pass(**kw):
    intake = Intake(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS, **kw)
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    runner = FakeRunner({"tecnica": VALID_OUTPUT, "producto_ux": "roto", "comercial+marketing": grouped})
    return run_pass(intake, runner)


def template_headers() -> list[str]:
    md = TEMPLATE.read_text(encoding="utf-8")
    block = md.split("```markdown", 1)[1].split("```", 1)[0]
    return [ln.strip() for ln in block.splitlines() if re.match(r"^#{2,3} ", ln.strip())]


def test_report_keeps_every_template_header_in_order():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    lines = [ln.strip() for ln in md.splitlines()]
    positions = [lines.index(h) for h in template_headers()]
    assert positions == sorted(positions)


def test_report_header_block():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    assert md.startswith("# MVP-UP · Producto Demo · 2026-10-04")
    assert "**Modo:** express · **Etapa:** mvp · **Objetivo de valor:** ingresos" in md
    # comercial(6×2)+marketing(6×2)+técnica(6) / 5 = 6,0 ; producto_ux sin evaluar
    assert "**Score global: 6,0/10** (ponderado por objetivo) · Pasada nº 1" in md


def test_unevaluated_and_na_rows():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    assert "| Producto / UX | sin evaluar | — | ⚪ |" in md
    assert "| Técnica | 6/10 | — | 🟡 |" in md


def test_na_dimension_listed_for_service():
    intake = Intake(product="Spa Demo", stage=Stage.IDEA, objective=Objective.INGRESOS,
                    add={"tecnica"}, has_software=False)
    runner = FakeRunner({"*": VALID_OUTPUT})
    md = render_markdown(build_report(run_pass(intake, runner), today=TODAY))
    assert "| Técnica | N/A | — | ⚪ |" in md


def test_findings_keep_evidence_and_missing_data_is_listed():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    assert "Evidencia: no existe carpeta tests/" in md
    assert "Volumen real de usuarios" in md


def test_save_report_writes_md_and_json_and_numbers_passes(tmp_path):
    report = build_report(express_pass(), today=TODAY)
    first = save_report(report, tmp_path)
    assert first.name == "2026-10-04-informe.md"
    data = json.loads(first.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["scores"]["tecnica"] == 6 and data["scores"]["producto_ux"] is None
    assert data["objective"] == "ingresos" and data["pass_number"] == 1
    second = save_report(build_report(express_pass(), today=TODAY, base_dir=tmp_path), tmp_path)
    assert second.name == "2026-10-04-informe-2.md"
    assert "Pasada nº 2" in second.read_text(encoding="utf-8")


@pytest.mark.parametrize("name, slug", [
    ("Producto Demo", "producto-demo"),
    ("../../etc/passwd", "etc-passwd"),
    ("Ñandú Café ☕", "nandu-cafe"),
])
def test_slugify_is_path_safe(name, slug):
    assert slugify(name) == slug


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        slugify("../..")


def test_report_dir_stays_inside_base(tmp_path):
    assert report_dir(tmp_path, "../../fuera").resolve().is_relative_to(tmp_path.resolve())


def test_ligera_report_uses_ligera_headers():
    intake = Intake(product="Semilla Demo", stage=Stage.IDEA, objective=Objective.DEPENDENCIA,
                    mode=Mode.LIGERA)
    md = render_markdown(build_report(run_pass(intake, FakeRunner({"*": LIGERA_OUTPUT})), today=TODAY))
    assert "## Score orientativo: 4/10" in md
    assert "## 3 tareas de reanudación" in md
    assert "1. Desplegar el prototipo" in md


def test_missing_data_is_deduplicated_across_dimensions():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    assert md.count("Volumen real de usuarios") == 1
    assert "- Volumen real de usuarios (Técnica, Comercial, Marketing y hype)" in md


# --- dry-run: el informe sintético se marca y nunca cuenta como pasada real ---

def synthetic_pass():
    from mvpup.dryrun import dry_run_responses
    from mvpup.selection import build_plan

    intake = Intake(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    plan = build_plan(intake)
    return run_pass(intake, FakeRunner(dry_run_responses(plan, intake.mode)), plan=plan)


def test_dry_run_report_is_marked_in_markdown_and_json():
    report = build_report(synthetic_pass(), today=TODAY, dry_run=True)
    md = render_markdown(report)
    assert "DRY-RUN" in md.splitlines()[2] or "DRY-RUN" in md.splitlines()[3]
    assert "NO es una auditoría" in md
    assert json.loads(json.dumps(report_to_json(report)))["dry_run"] is True


def test_dry_run_report_file_is_not_a_pass_and_ignores_previous_passes(tmp_path):
    real = save_report(build_report(express_pass(), today=TODAY, base_dir=tmp_path), tmp_path)
    assert real.name == "2026-10-04-informe.md"
    dry = save_report(build_report(synthetic_pass(), today=TODAY, base_dir=tmp_path, dry_run=True), tmp_path)
    assert dry.name == "2026-10-04-dry-run.md"
    assert "Pasada nº 1" in dry.read_text(encoding="utf-8")  # no compara con la pasada real
    # la siguiente pasada real sigue siendo la nº 2: el dry-run no cuenta
    nxt = build_report(express_pass(), today=TODAY, base_dir=tmp_path)
    assert nxt.pass_number == 2


def test_real_report_has_no_dry_run_marker():
    md = render_markdown(build_report(express_pass(), today=TODAY))
    assert "DRY-RUN" not in md
    assert report_to_json(build_report(express_pass(), today=TODAY))["dry_run"] is False


def test_ligera_report_lists_findings_discarded_for_lack_of_evidence():
    intake = Intake(product="Semilla Demo", stage=Stage.IDEA, objective=Objective.DEPENDENCIA,
                    mode=Mode.LIGERA)
    result = run_pass(intake, FakeRunner({"*": LIGERA_OUTPUT}))  # H2 lleva «Evidencia: N/D»
    md = render_markdown(build_report(result, today=TODAY))
    assert "H2 descartado: sin evidencia" in md
    assert any("ligera: aviso: H2 descartado" in ln for ln in result.log)


# --- loop 5: el semáforo debe coincidir con el score que se muestra ---

def test_status_icon_matches_the_displayed_rounded_score():
    intake = Intake(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    runner = FakeRunner({"tecnica": VALID_OUTPUT.replace("6/10", "6,96/10"),
                         "producto_ux": VALID_OUTPUT.replace("6/10", "4,97/10"),
                         "comercial+marketing": grouped})
    md = render_markdown(build_report(run_pass(intake, runner), today=TODAY))
    assert "| Técnica | 7,0/10 | — | 🟢 |" in md
    assert "| Producto / UX | 5,0/10 | — | 🟡 |" in md


# --- Roadmap: campos ausentes se omiten y se cuentan UNA vez --------------------------------------


def _roadmap_section(md: str) -> str:
    return md.split("## Roadmap de escalado", 1)[1].split("## Evolución", 1)[0]


def test_roadmap_lines_omit_unknown_cost_and_owner():
    section = _roadmap_section(render_markdown(build_report(express_pass(), today=TODAY)))
    assert "N/D" not in section and "por decidir" not in section and "ejecutable por" not in section
    assert "- [ ] Añadir pytest con un test de humo · sube Técnica" in section


def test_roadmap_counts_missing_cost_and_owner_once():
    report = build_report(express_pass(), today=TODAY)
    section = _roadmap_section(render_markdown(report))
    total = len(report.roadmap.all_items())
    lines = [ln for ln in section.splitlines() if "sin coste estimado" in ln]
    assert len(lines) == 1
    assert f"{total} de {total} acciones sin coste estimado" in lines[0]
    assert f"{total} de {total} sin ejecutor asignado" in lines[0]


def test_roadmap_prints_cost_and_owner_when_known():
    from dataclasses import replace

    from mvpup.roadmap import Horizon

    report = build_report(express_pass(), today=TODAY)
    items = report.roadmap.by_horizon[Horizon.H1]
    items[0] = replace(items[0], cost="2 h", owner="operador")
    section = _roadmap_section(render_markdown(report))
    assert "· ~2 h · sube" in section and "· ejecutable por: operador" in section
    total = len(report.roadmap.all_items())
    assert f"{total - 1} de {total} acciones sin coste estimado" in section


def test_roadmap_states_its_horizon_rule():
    section = _roadmap_section(render_markdown(build_report(express_pass(), today=TODAY)))
    assert "Regla de horizonte" in section and "impacto × esfuerzo" in section


def test_json_roadmap_keeps_cost_and_owner_as_null_when_unknown():
    data = report_to_json(build_report(express_pass(), today=TODAY))
    assert data["roadmap"] and all(i["cost"] is None and i["owner"] is None for i in data["roadmap"])


# --- Matriz: una línea corta por ítem; el detalle vive en el roadmap ------------------------------


def _matrix_cells(md: str) -> list[str]:
    section = md.split("## Matriz impacto × esfuerzo", 1)[1].split("## Roadmap de escalado", 1)[0]
    rows = [ln for ln in section.splitlines() if ln.startswith("| **Impacto")]
    return [cell.strip() for row in rows for cell in row.strip("|").split(" | ")[1:]]


def _items(cell: str) -> list[str]:
    return cell.split(": ", 1)[1].split("<br>")


def _paragraph_pass():
    """Como la primera pasada real: hallazgos de un párrafo entero, con y sin acción."""
    from mvpup.parsing import DimensionResult, Finding, Level

    paragraph = ("La economía unitaria no está cerrada. " + "El punto de equilibrio depende de un dato sin verificar. " * 6).strip()
    result = express_pass()
    result.results = {
        next(iter(result.results)): DimensionResult(score=5, findings=[
            Finding("H1", paragraph, Level.ALTO, Level.BAJO, "docs/oferta.md §6", action="Cerrar la economía unitaria con el gestor"),
            Finding("H2", paragraph.replace("economía", "tesorería"), Level.ALTO, Level.MEDIO, "docs/oferta.md §7"),
            Finding("H3", "Texto | con barra", Level.MEDIO, Level.BAJO, "README.md", action="Quitar la barra | del texto"),
        ])
    }
    return result


def test_matrix_cells_hold_one_short_line_per_item():
    from mvpup.report import MATRIX_ITEM_CHARS

    md = render_markdown(build_report(_paragraph_pass(), today=TODAY))
    items = [item for cell in _matrix_cells(md) if cell.split(": ", 1)[1] != "—" for item in _items(cell)]
    assert len(items) == 3
    for item in items:
        title, dim = item.rsplit(" (", 1)
        assert len(title) <= MATRIX_ITEM_CHARS and dim == "Técnica)"
        assert "Evidencia" not in item  # el detalle no va en la celda


def test_matrix_shows_the_action_or_the_truncated_finding():
    md = render_markdown(build_report(_paragraph_pass(), today=TODAY))
    quick, bets, later, _ = _matrix_cells(md)
    assert _items(quick) == ["Cerrar la economía unitaria con el gestor (Técnica)"]
    (bet,) = _items(bets)
    assert bet.startswith("La tesorería unitaria no está cerrada.") and bet.endswith("… (Técnica)")
    assert _items(later) == ["Quitar la barra \\| del texto (Técnica)"]  # la barra no rompe la tabla


def test_detail_dropped_from_the_matrix_is_still_in_the_roadmap():
    md = render_markdown(build_report(_paragraph_pass(), today=TODAY))
    roadmap = md.split("## Roadmap de escalado", 1)[1].split("## Evolución", 1)[0]
    assert "El punto de equilibrio depende de un dato sin verificar. " * 5 in roadmap
    assert "Evidencia: docs/oferta.md §6" in roadmap and "Evidencia: docs/oferta.md §7" in roadmap


def test_discarded_findings_keep_their_detail_outside_the_matrix():
    """Lo que la matriz descarta no entra en el roadmap, pero su evidencia no puede perderse del informe."""
    md = render_markdown(build_report(express_pass(), today=TODAY))  # H3 de VALID_OUTPUT es M/A → descartar
    roadmap = md.split("## Roadmap de escalado", 1)[1].split("## Evolución", 1)[0]
    lines = roadmap.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Descartado por la matriz"))
    assert (
        "- Arquitectura monolítica (Técnica · Evidencia: app.py de 2.000 líneas) · "
        "acción propuesta: Separar la aplicación en módulos"
    ) in lines[start + 1:start + 4]  # una línea por dimensión que lo citó
    assert "- [ ] Separar la aplicación en módulos" not in roadmap  # sigue sin programarse
