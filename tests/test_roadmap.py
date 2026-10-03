from mvpup.consolidation import build_matrix, structural_findings
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective
from mvpup.parsing import DimensionResult, Finding, Level
from mvpup.roadmap import Horizon, build_roadmap, top_five

A, M, B = Level.ALTO, Level.MEDIO, Level.BAJO


def f(id_, text, imp, eff):
    return Finding(id=id_, text=text, impact=imp, effort=eff, evidence="README.md")


def res(*findings):
    return DimensionResult(score=5, findings=list(findings))


RESULTS = {
    D.COMERCIAL: res(
        f("H1", "Publicar precios", A, B),
        f("H2", "Diseñar programa de partners", A, A),  # comercial ×2 en ingresos → H3
    ),
    D.TECNICA: res(
        f("H1", "Migrar base de datos", A, A),  # técnica ×1 en ingresos → no justifica H3
        f("H2", "Añadir CI", A, M),
        f("H3", "Limpiar logs", M, B),
        f("H4", "Reescribir en Rust", B, A),  # descartar → fuera del roadmap
    ),
}


def roadmap(objective=Objective.INGRESOS, in_wip=True):
    matrix = build_matrix(RESULTS, objective)
    return build_roadmap(matrix, objective, in_wip_lanes=in_wip)


def texts(items):
    return [i.entry.finding.text for i in items]


def test_horizons_map_from_quadrants():
    r = roadmap()
    assert texts(r.items(Horizon.H1)) == ["Publicar precios"]
    assert texts(r.items(Horizon.H2)) == ["Añadir CI", "Limpiar logs"]
    assert texts(r.items(Horizon.H3)) == ["Diseñar programa de partners"]


def test_high_effort_bets_without_objective_justification_are_not_scheduled():
    r = roadmap()
    assert "Migrar base de datos" in texts(r.not_justified)
    assert "Migrar base de datos" not in texts(r.all_items())


def test_objective_changes_which_bets_are_justified():
    r = roadmap(objective=Objective.VENDIBLE)  # técnica ×2, comercial ×1
    assert texts(r.items(Horizon.H3)) == ["Migrar base de datos"]


def test_discarded_findings_never_enter_roadmap():
    assert "Reescribir en Rust" not in texts(roadmap().all_items())


def test_costs_are_never_invented():
    assert all(i.cost == "N/D" for i in roadmap().all_items())


def test_out_of_wip_lanes_marks_everything_as_queued():
    r = roadmap(in_wip=False)
    assert r.wip_note
    assert all(i.queued for i in r.all_items())
    assert roadmap().wip_note == ""


def test_top_five_puts_structural_first_then_quick_wins():
    results = dict(RESULTS)
    results[D.MARKETING] = res(f("H1", "Sin analítica web instalada", A, M))
    results[D.DATOS] = res(f("H1", "No hay analítica web instalada", A, M))
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    top = top_five(rm)
    assert len(top) == 5
    assert "analítica" in top[0].lower()
    assert top[1].startswith("Publicar precios")
    assert len(set(top)) == 5


def test_low_impact_low_effort_goes_to_backlog_not_h2():
    results = {D.LEGAL: res(f("H1", "Pulir textos", B, B), f("H2", "Añadir aviso cookies", M, B))}
    r = build_roadmap(build_matrix(results, Objective.INGRESOS), Objective.INGRESOS)
    assert texts(r.items(Horizon.H2)) == ["Añadir aviso cookies"]
    assert texts(r.backlog) == ["Pulir textos"]


def test_structural_only_enters_top_if_scheduled():
    results = {
        D.COMERCIAL: res(f("H1", "Migrar CRM legado completo", B, A)),
        D.OPERATIVA: res(f("H1", "Migrar CRM legado entero", B, A)),
    }
    matrix = build_matrix(results, Objective.INGRESOS)
    assert structural_findings(results)  # existe el estructural…
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    assert top_five(rm) == []  # …pero es «descartar»


def test_top_five_marks_queued_when_out_of_wip():
    matrix = build_matrix(RESULTS, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, in_wip_lanes=False)
    assert all(t.endswith("· encolar") for t in top_five(rm))


def test_costs_from_a_source_are_used():
    matrix = build_matrix(RESULTS, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, costs={(D.COMERCIAL, "H1"): "2 h (operador)"})
    assert rm.items(Horizon.H1)[0].cost == "2 h (operador)"
    assert rm.items(Horizon.H2)[0].cost == "N/D"


def test_structural_dimensions_only_count_scheduled_entries():
    results = {
        D.COMERCIAL: res(f("H1", "Sin CRM centralizado", A, B)),  # programado (H1)
        D.OPERATIVA: res(f("H1", "Sin CRM centralizado", B, A)),  # descartar
    }
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    assert top_five(rm) == ["Sin CRM centralizado · Comercial · H1"]


def _structural_case():
    return {
        D.COMERCIAL: res(f("H1", "Sin analítica web instalada", A, B)),
        D.MARKETING: res(f("H1", "No hay analítica web instalada", A, M)),
        D.TECNICA: res(f("H1", "Añadir CI", A, M)),
    }


def test_structural_entries_merge_into_one_roadmap_action():
    results = _structural_case()
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    actions = rm.all_items()
    merged = [i for i in actions if i.related]
    assert len(merged) == 1
    assert merged[0].horizon is Horizon.H1  # el horizonte más temprano del grupo
    assert {merged[0].entry.dimension, *[e.dimension for e in merged[0].related]} == {
        D.COMERCIAL, D.MARKETING}
    assert texts(actions).count("No hay analítica web instalada") == 0
    assert len(actions) == 2  # analítica (fusionada) + CI


def test_merged_action_lists_all_dimensions_it_raises():
    results = _structural_case()
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    merged = next(i for i in rm.all_items() if i.related)
    assert merged.dimension_labels == "Comercial + Marketing y hype"


def test_top_five_marks_merged_actions_as_structural():
    results = _structural_case()
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    top = top_five(rm)
    assert top[0].startswith("[estructural] Sin analítica web instalada · Comercial + Marketing y hype")
    assert len(top) == 2


def test_merged_action_keeps_every_known_cost():
    results = _structural_case()
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(
        matrix, Objective.INGRESOS, structural=structural_findings(results),
        costs={(D.COMERCIAL, "H1"): "2 h", (D.MARKETING, "H1"): "5 h"},
    )
    merged = next(i for i in rm.all_items() if i.related)
    assert merged.cost == "Comercial: 2 h; Marketing y hype: 5 h"


def test_merged_action_marks_partial_costs():
    results = _structural_case()
    matrix = build_matrix(results, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results),
                       costs={(D.MARKETING, "H1"): "5 h"})
    merged = next(i for i in rm.all_items() if i.related)
    assert merged.cost == "Marketing y hype: 5 h; Comercial: N/D"
    rm2 = build_roadmap(matrix, Objective.INGRESOS, structural=structural_findings(results))
    assert next(i for i in rm2.all_items() if i.related).cost == "N/D"
