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


def test_horizons_map_from_impact_effort_and_objective():
    r = roadmap()  # ingresos: comercial pesa ×2, técnica ×1 (baja un horizonte salvo quick wins)
    assert texts(r.items(Horizon.H1)) == ["Publicar precios"]
    assert texts(r.items(Horizon.H2)) == []
    assert texts(r.items(Horizon.H3)) == ["Diseñar programa de partners", "Añadir CI", "Limpiar logs"]


def test_priority_dimensions_keep_their_base_horizon():
    r = roadmap(objective=Objective.VENDIBLE)  # técnica ×2, comercial ×1
    assert texts(r.items(Horizon.H2)) == ["Añadir CI", "Limpiar logs"]


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
    assert rm.items(Horizon.H3)[0].cost == "N/D"  # sin fuente: no se inventa


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


# --- loop 2: Horizon.label (no `title`, que pisa str.title) ---

def test_horizon_label_does_not_shadow_str_title():
    from mvpup.roadmap import Horizon

    assert Horizon.H1.label == "Esta semana (quick wins)"
    assert Horizon.H3.label == "Trimestre"
    assert Horizon.H1.title() == "H1"  # el método de str sigue siendo el de str


# --- Regla de horizonte explícita (impacto × esfuerzo, ajustada por el objetivo de valor) -------


def _many(dim, prefix, imp, eff, n):
    return [f(f"H{i}", f"{prefix} {dim.value} {i}", imp, eff) for i in range(1, n + 1)]


def test_horizon_rule_table_is_explicit_and_complete():
    from mvpup.roadmap import HORIZON_RULE

    assert HORIZON_RULE == {
        (A, B): Horizon.H1, (A, M): Horizon.H2, (A, A): Horizon.H3, (M, B): Horizon.H2,
    }


def test_a_real_shaped_pass_no_longer_dumps_almost_everything_into_h2():
    """Reparto de la primera pasada real (express, objetivo ingresos): 1 A/B, 8 A/M, 8 M/B.

    Con la regla anterior, 16 de 17 acciones caían en H2.
    """
    results = {
        D.COMERCIAL: res(f("H1", "quick win comercial", A, B), *_many(D.COMERCIAL, "apuesta", A, M, 2),
                         *[f(f"H{i}", f"menor comercial {i}", M, B) for i in (4, 5)]),
        D.MARKETING: res(*_many(D.MARKETING, "apuesta", A, M, 1),
                         *[f(f"H{i}", f"menor marketing {i}", M, B) for i in (2, 3)]),
        D.TECNICA: res(*_many(D.TECNICA, "apuesta", A, M, 2),
                       *[f(f"H{i}", f"menor tecnica {i}", M, B) for i in (3, 4)]),
        D.PRODUCTO_UX: res(*_many(D.PRODUCTO_UX, "apuesta", A, M, 3),
                           *[f(f"H{i}", f"menor ux {i}", M, B) for i in (4, 5)]),
    }
    r = build_roadmap(build_matrix(results, Objective.INGRESOS), Objective.INGRESOS)
    sizes = {h: len(r.items(h)) for h in Horizon}
    assert sum(sizes.values()) == 17
    assert sizes == {Horizon.H1: 1, Horizon.H2: 7, Horizon.H3: 9}
    # H2 = lo que mueve el objetivo (dimensiones ×2); el resto baja un horizonte.
    assert {i.entry.dimension for i in r.items(Horizon.H2)} == {D.COMERCIAL, D.MARKETING}
    assert {i.entry.dimension for i in r.items(Horizon.H3)} == {D.TECNICA, D.PRODUCTO_UX}


def test_quick_wins_are_never_deferred_even_outside_priority_dimensions():
    results = {D.TECNICA: res(f("H1", "Arreglar el build", A, B)),
               D.COMERCIAL: res(f("H1", "Definir la oferta", A, M))}
    r = build_roadmap(build_matrix(results, Objective.INGRESOS), Objective.INGRESOS)
    assert texts(r.items(Horizon.H1)) == ["Arreglar el build"]


def test_without_any_priority_dimension_nothing_is_deferred():
    """Si ninguna dimensión evaluada pesa ×2 no hay con qué priorizar: no se vacía H2 hacia H3."""
    results = {D.TECNICA: res(f("H1", "Añadir CI", A, M), f("H2", "Limpiar logs", M, B))}
    r = build_roadmap(build_matrix(results, Objective.INGRESOS), Objective.INGRESOS)
    assert texts(r.items(Horizon.H2)) == ["Añadir CI", "Limpiar logs"]
    assert r.items(Horizon.H3) == []


def test_each_item_records_the_rule_that_placed_it():
    r = roadmap()
    by_text = {i.entry.finding.text: i for i in r.all_items()}
    assert by_text["Publicar precios"].deferred is False
    assert by_text["Añadir CI"].deferred is True  # técnica no es prioritaria para «ingresos»


def test_unknown_cost_and_owner_are_flagged_not_printed():
    r = roadmap()
    assert all(not i.has_cost and not i.has_owner for i in r.all_items())
    matrix = build_matrix(RESULTS, Objective.INGRESOS)
    rm = build_roadmap(matrix, Objective.INGRESOS, costs={(D.COMERCIAL, "H1"): "2 h (operador)"})
    assert rm.items(Horizon.H1)[0].has_cost
