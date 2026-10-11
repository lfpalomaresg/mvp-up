"""`mvpup compare <anterior> <nuevo>`: deltas entre dos informes ya guardados. Datos sintéticos."""

import json
from pathlib import Path

import pytest

from mvpup.cli import main
from mvpup.compare import diff_reports, render_diff
from mvpup.dimensions import Dimension as D


def _report(**fields):
    base = {
        "schema": 1, "product": "Producto Demo", "slug": "producto-demo", "date": "2026-09-01",
        "mode": "express", "stage": "mvp", "objective": "ingresos", "global_score": 5.0,
        "scores": {"tecnica": 4, "producto_ux": 6, "comercial": 5, "marketing": None},
        "roadmap": [
            {"horizon": "H1", "dimension": "tecnica", "dimensions": ["tecnica"], "action": "Sin tests automatizados"},
            {"horizon": "H2", "dimension": "comercial", "dimensions": ["comercial"], "action": "Oferta sin garantía"},
        ],
        "findings": [
            {"dimension": "tecnica", "id": "H1", "text": "Sin tests automatizados", "impact": "A"},
            {"dimension": "comercial", "id": "H1", "text": "Oferta sin garantía", "impact": "A"},
            {"dimension": "comercial", "id": "H2", "text": "Pricing sin justificar", "impact": "M"},
        ],
    }
    base.update(fields)
    return base


def _newer(**fields):
    base = _report(
        date="2026-10-04", global_score=6.2,
        scores={"tecnica": 7, "producto_ux": 6, "comercial": 4, "marketing": 5},
        roadmap=[
            {"horizon": "H1", "dimension": "comercial", "dimensions": ["comercial"], "action": "Oferta sin garantía"},
            {"horizon": "H1", "dimension": "marketing", "dimensions": ["marketing"], "action": "Sin prueba social"},
        ],
        findings=[
            {"dimension": "comercial", "id": "H1", "text": "Oferta sin garantía", "impact": "A"},
            {"dimension": "comercial", "id": "H2", "text": "Pricing sin justificar", "impact": "M"},
            {"dimension": "marketing", "id": "H1", "text": "Sin prueba social", "impact": "A"},
        ],
    )
    base.update(fields)
    return base


def test_diff_has_a_delta_row_per_dimension_in_canonical_order():
    diff = diff_reports(_report(), _newer())
    dims = [row.dimension for row in diff.rows]
    assert dims == [D.TECNICA, D.PRODUCTO_UX, D.COMERCIAL, D.MARKETING]
    by_dim = {row.dimension: row for row in diff.rows}
    assert by_dim[D.TECNICA].delta == "+3"
    assert by_dim[D.PRODUCTO_UX].delta == "="
    assert by_dim[D.COMERCIAL].delta == "🔴 -1"
    assert by_dim[D.MARKETING].delta == "nuevo"  # antes sin evaluar
    assert diff.global_delta == "+1,2"


def test_diff_classifies_closed_new_and_open_actions():
    diff = diff_reports(_report(), _newer())
    assert diff.closed == ["Sin tests automatizados"]  # ya no está ni en el roadmap ni en los hallazgos
    assert diff.new == ["Sin prueba social"]
    assert diff.open == ["Oferta sin garantía"]


def test_action_that_left_the_roadmap_but_is_still_a_finding_is_not_closed():
    newer = _newer(roadmap=[])
    diff = diff_reports(_report(), newer)
    assert "Oferta sin garantía" not in diff.closed
    assert "Oferta sin garantía" in diff.open


def test_diff_warns_on_objective_change_and_marks_deltas_not_comparable():
    diff = diff_reports(_report(), _newer(objective="vendible"))
    assert any("no comparables" in w for w in diff.warnings)
    assert {row.dimension: row.delta for row in diff.rows}[D.TECNICA] == "n/c (4→7)"
    assert diff.global_delta.startswith("n/c")


def test_diff_warns_on_different_product_inverted_order_and_dry_run():
    diff = diff_reports(_newer(), _report(product="Otro Producto", slug="otro-producto", dry_run=True))
    joined = "\n".join(diff.warnings)
    assert "productos distintos" in joined
    assert "anterior a la pasada" in joined or "orden" in joined
    assert "DRY-RUN" in joined


def test_diff_warns_on_stale_previous_and_stage_change():
    diff = diff_reports(_report(date="2026-01-01"), _newer(stage="produccion"))
    joined = "\n".join(diff.warnings)
    assert "6 meses" in joined and "etapa" in joined


def test_diff_tolerates_corrupt_fields_in_either_report():
    diff = diff_reports(_report(scores="x", roadmap="nada"), _newer(global_score="alto"))
    assert diff.rows and any("ilegibles" in w for w in diff.warnings)


def test_render_diff_is_markdown_with_the_expected_sections():
    md = render_diff(diff_reports(_report(), _newer()))
    assert md.startswith("# MVP-UP · Comparación · Producto Demo")
    for header in ("## Δ por dimensión", "## Acciones cerradas", "## Acciones nuevas", "## Acciones que siguen abiertas"):
        assert header in md
    assert "| Técnica | 4/10 | 7/10 | +3 |" in md
    assert "2026-09-01" in md and "2026-10-04" in md
    assert "5,0/10" in md and "6,2/10" in md and "+1,2" in md
    assert "- ✅? Sin tests automatizados" in md
    assert "- 🆕 Sin prueba social" in md
    assert "- ⏳ Oferta sin garantía" in md


# --- CLI: dos informes sintéticos generados por el dry-run ---

BASE = ["run", "--product", "Producto Demo", "--objective", "ingresos", "--stage", "mvp"]


def _dry_run(tmp_path: Path, name: str, *extra: str) -> Path:
    out = tmp_path / name
    assert main([*BASE, *extra, "--dry-run", "--out", str(out)]) == 0
    return next((out / "producto-demo").glob("*-dry-run.md"))


@pytest.fixture
def two_dry_runs(tmp_path, capsys):
    older = _dry_run(tmp_path, "a")
    newer = _dry_run(tmp_path, "b", "--add", "seguridad", "--remove", "marketing")
    # Mismo producto, misma fecha: se simula una pasada posterior con un score distinto (sintético).
    data = json.loads(newer.with_suffix(".json").read_text(encoding="utf-8"))
    data["date"] = "2099-01-02"
    data["scores"]["tecnica"] = 8
    newer.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    return older, newer


def test_cli_compare_prints_markdown_with_deltas_and_actions(two_dry_runs, capsys):
    older, newer = two_dry_runs
    assert main(["compare", str(older), str(newer)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# MVP-UP · Comparación · Producto Demo")
    assert "| Técnica | 6/10 | 8/10 | +2 |" in out
    assert "| Seguridad | — | 4/10 | nuevo |" in out
    assert "| Marketing y hype | 3/10 | — | — |" in out
    assert "🆕" in out and "✅?" in out and "⏳" in out
    assert "DRY-RUN" in out  # los dos son sintéticos: se avisa


def test_cli_compare_accepts_json_paths_and_saves_markdown(two_dry_runs, tmp_path, capsys):
    older, newer = two_dry_runs
    target = tmp_path / "comparacion.md"
    assert main(["compare", str(older.with_suffix(".json")), str(newer.with_suffix(".json")),
                 "--save", str(target)]) == 0
    assert "Comparación guardada" in capsys.readouterr().out
    assert target.read_text(encoding="utf-8").startswith("# MVP-UP · Comparación")


def test_cli_compare_rejects_missing_or_invalid_reports(tmp_path, two_dry_runs, capsys):
    older, _ = two_dry_runs
    assert main(["compare", str(older), str(tmp_path / "no-existe.md")]) == 2
    assert "Traceback" not in capsys.readouterr().err
    bad = tmp_path / "2026-01-01-informe.md"
    bad.write_text("# sin json gemelo", encoding="utf-8")
    assert main(["compare", str(bad), str(older)]) == 2
    assert "JSON" in capsys.readouterr().err
    notreport = tmp_path / "x.json"
    notreport.write_text('{"hola": 1}', encoding="utf-8")
    assert main(["compare", str(notreport), str(older)]) == 2
    assert "informe" in capsys.readouterr().err
