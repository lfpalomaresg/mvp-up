import json

import pytest

from support import write_report as write
from mvpup.portfolio import load_latest_reports, render_portfolio, synthesize




def test_loads_only_latest_report_per_product(cartera):
    latest = load_latest_reports(cartera)
    assert {r["slug"]: r["date"] for r in latest} == {
        "app-uno": "2026-10-01", "app-dos": "2026-10-02", "app-tres": "2026-10-03"}


def test_needs_two_projects(tmp_path):
    write(tmp_path, "sola", "2026-10-01", {"tecnica": 5}, 5.0)
    with pytest.raises(ValueError, match="2"):
        synthesize(load_latest_reports(tmp_path))


def test_detects_transversal_patterns(cartera):
    s = synthesize(load_latest_reports(cartera))
    text = "\n".join(s.patterns)
    # técnica supera a comercial en los 3 proyectos
    assert "Técnica > Comercial en 3/3" in text
    # comercial ≤4 en todos → debilidad transversal
    assert "Comercial" in text and "débil" in text
    # datos sin evaluar en 2/3
    assert "Datos y medición: sin medir en 2/3" in text


def test_ranking_by_global_score(cartera):
    s = synthesize(load_latest_reports(cartera))
    assert [r["slug"] for r in s.ranking_by_objective["ingresos"]] == ["app-dos", "app-uno", "app-tres"]


def test_mixed_objectives_warns(cartera):
    write(cartera, "app-cuatro", "2026-10-03", {"tecnica": 5}, 5.0, objective="vendible")
    s = synthesize(load_latest_reports(cartera))
    assert any("objetivos de valor distintos" in p for p in s.patterns)
    assert set(s.ranking_by_objective) == {"ingresos", "vendible"}


def test_render_portfolio_markdown(cartera):
    md = render_portfolio(synthesize(load_latest_reports(cartera)))
    assert md.startswith("# MVP-UP · Síntesis de cartera")
    assert "| App Dos | 5,0/10 | 2026-10-02 |" in md


def test_corrupt_json_is_skipped(cartera):
    (cartera / "app-dos" / "2026-10-05-informe.json").write_text("{roto", encoding="utf-8")
    latest = load_latest_reports(cartera)
    assert {r["slug"]: r["date"] for r in latest}["app-dos"] == "2026-10-02"



def test_weak_dimension_needs_enough_coverage(tmp_path):
    for i in range(4):
        scores = {"tecnica": 6, "comercial": 3} if i < 2 else {"tecnica": 6}
        write(tmp_path, f"app-{i}", "2026-10-01", scores, 5.0)
    text = "\n".join(synthesize(load_latest_reports(tmp_path)).patterns)
    assert "débil en toda la cartera" not in text
    assert "Comercial: débil donde se evaluó (2/4)" in text


def test_absent_dimensions_count_as_blind_spot(tmp_path):
    write(tmp_path, "app-a", "2026-10-01", {"tecnica": 6}, 6.0)
    write(tmp_path, "app-b", "2026-10-01", {"tecnica": 5}, 5.0)
    text = "\n".join(synthesize(load_latest_reports(tmp_path)).patterns)
    assert "Datos y medición: sin medir en 2/2" in text


def test_ranking_is_grouped_by_objective_when_they_differ(cartera):
    write(cartera, "app-cuatro", "2026-10-03", {"tecnica": 9}, 9.0, objective="vendible")
    s = synthesize(load_latest_reports(cartera))
    assert list(s.ranking_by_objective) == ["ingresos", "vendible"]
    assert [r["slug"] for r in s.ranking_by_objective["ingresos"]] == ["app-dos", "app-uno", "app-tres"]
    md = render_portfolio(s)
    assert "### Objetivo: vendible" in md


def test_semantically_invalid_report_falls_back_to_previous(cartera):
    bad = {"schema": 1, "slug": "app-dos", "date": "2026-10-09", "objective": "ingresos",
           "global_score": "alto", "scores": {"tecnica": 7}}
    (cartera / "app-dos" / "2026-10-09-informe.json").write_text(json.dumps(bad), encoding="utf-8")
    latest = {r["slug"]: r["date"] for r in load_latest_reports(cartera)}
    assert latest["app-dos"] == "2026-10-02"
    synthesize(load_latest_reports(cartera))  # no revienta


def test_badly_named_files_are_ignored(cartera):
    (cartera / "app-dos" / "zzz-informe.json").write_text(
        json.dumps({"scores": {"tecnica": 1}, "global_score": 1.0, "date": "x"}), encoding="utf-8")
    assert {r["slug"]: r["date"] for r in load_latest_reports(cartera)}["app-dos"] == "2026-10-02"


def test_single_weak_evaluation_is_reported_as_partial(tmp_path):
    write(tmp_path, "app-a", "2026-10-01", {"tecnica": 6, "comercial": 3}, 5.0)
    write(tmp_path, "app-b", "2026-10-01", {"tecnica": 6}, 6.0)
    text = "\n".join(synthesize(load_latest_reports(tmp_path)).patterns)
    assert "Comercial: débil donde se evaluó (1/2)" in text


@pytest.mark.parametrize("mutation", [
    {"schema": 999}, {"objective": None}, {"global_score": "x"},
])
def test_strict_schema_falls_back_to_previous(cartera, mutation):
    data = {"schema": 1, "slug": "app-dos", "date": "2026-10-09", "objective": "ingresos",
            "global_score": 7.0, "scores": {"tecnica": 7}}
    data.update(mutation)
    if mutation.get("objective", "") is None:
        del data["objective"]
    (cartera / "app-dos" / "2026-10-09-informe.json").write_text(json.dumps(data), encoding="utf-8")
    assert {r["slug"]: r["date"] for r in load_latest_reports(cartera)}["app-dos"] == "2026-10-02"


def test_coverage_table_shows_every_dimension(cartera):
    md = render_portfolio(synthesize(load_latest_reports(cartera)))
    assert "## Cobertura por dimensión" in md
    assert "| Datos y medición | 1/3 |" in md
    assert "| Legal | 0/3 |" in md


def test_boolean_schema_is_rejected(cartera):
    data = {"schema": True, "slug": "app-dos", "date": "2026-10-09", "objective": "ingresos",
            "global_score": 7.0, "scores": {"tecnica": 7}}
    (cartera / "app-dos" / "2026-10-09-informe.json").write_text(json.dumps(data), encoding="utf-8")
    assert {r["slug"]: r["date"] for r in load_latest_reports(cartera)}["app-dos"] == "2026-10-02"


def test_zero_score_ranks_above_missing_score(tmp_path):
    write(tmp_path, "a-sin-score", "2026-10-01", {"tecnica": None}, None)
    write(tmp_path, "z-cero", "2026-10-01", {"tecnica": 0}, 0.0)
    s = synthesize(load_latest_reports(tmp_path))
    assert [r["slug"] for r in s.ranking_by_objective["ingresos"]] == ["z-cero", "a-sin-score"]
