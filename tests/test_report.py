import json
import re
from datetime import date
from pathlib import Path

import pytest

from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.report import build_report, render_markdown, report_dir, save_report, slugify
from mvpup.runners import FakeRunner
from mvpup.parsing import GROUP_SEPARATOR
from support import LIGERA_OUTPUT, VALID_OUTPUT

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
