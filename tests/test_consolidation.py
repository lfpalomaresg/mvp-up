from mvpup.consolidation import Quadrant, build_matrix, structural_findings
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective
from mvpup.parsing import DimensionResult, Finding, Level

A, M, B = Level.ALTO, Level.MEDIO, Level.BAJO


def f(id_, text, imp, eff, ev="README.md"):
    return Finding(id=id_, text=text, impact=imp, effort=eff, evidence=ev)


def res(*findings, score=5):
    return DimensionResult(score=score, findings=list(findings))


def test_quadrants_follow_report_template():
    results = {
        D.TECNICA: res(
            f("H1", "Sin tests", A, B),
            f("H2", "Reescribir backend", A, A),
            f("H3", "Renombrar variables", M, B),
            f("H4", "Migrar a microservicios", B, A),
            f("H5", "Documentar API", B, M),
        )
    }
    m = build_matrix(results, Objective.INGRESOS)
    assert [e.finding.id for e in m[Quadrant.QUICK_WINS]] == ["H1"]
    assert [e.finding.id for e in m[Quadrant.APUESTAS]] == ["H2"]
    assert [e.finding.id for e in m[Quadrant.SI_SOBRA_TIEMPO]] == ["H3"]
    assert {e.finding.id for e in m[Quadrant.DESCARTAR]} == {"H4", "H5"}


def test_every_finding_lands_in_exactly_one_quadrant():
    results = {
        D.COMERCIAL: res(f("H1", "a", A, B), f("H2", "b", M, M)),
        D.LEGAL: res(f("H1", "c", B, B)),
    }
    m = build_matrix(results, Objective.INGRESOS)
    assert sum(len(v) for v in m.values()) == 3


def test_quick_wins_sorted_by_priority_dimension_of_objective():
    # Objetivo ingresos: comercial pesa ×2, legal ×1 → comercial primero
    results = {
        D.LEGAL: res(f("H1", "Aviso legal", A, B)),
        D.COMERCIAL: res(f("H1", "Publicar precios", A, B)),
    }
    qw = build_matrix(results, Objective.INGRESOS)[Quadrant.QUICK_WINS]
    assert [e.dimension for e in qw] == [D.COMERCIAL, D.LEGAL]


def test_structural_findings_detect_shared_root_across_dimensions():
    results = {
        D.COMERCIAL: res(f("H1", "No hay analítica instalada en la web", A, B)),
        D.MARKETING: res(f("H2", "Sin analítica web instalada: no se mide conversión", A, M)),
        D.TECNICA: res(f("H1", "Sin tests automatizados", A, B)),
    }
    structural = structural_findings(results)
    assert len(structural) == 1
    assert set(structural[0].dimensions) == {D.COMERCIAL, D.MARKETING}


def test_same_dimension_repetition_is_not_structural():
    results = {
        D.TECNICA: res(
            f("H1", "Sin analítica instalada", A, B), f("H2", "Analítica no instalada", A, B)
        )
    }
    assert structural_findings(results) == []


def test_structural_findings_capped_at_three():
    topics = ["analítica instalada web", "precios publicados web", "aviso legal publicado",
              "backups configurados servidor"]
    results = {
        D.COMERCIAL: res(*[f(f"H{i}", f"Sin {t}", A, B) for i, t in enumerate(topics, 1)]),
        D.MARKETING: res(*[f(f"H{i}", f"No hay {t}", A, B) for i, t in enumerate(topics, 1)]),
    }
    assert len(structural_findings(results)) == 3


def test_single_token_equivalents_are_structural():
    results = {
        D.COMERCIAL: res(f("H1", "Sin analítica", A, B)),
        D.MARKETING: res(f("H1", "No hay analítica", A, B)),
    }
    assert len(structural_findings(results)) == 1


def test_single_shared_token_with_extra_words_is_not_enough():
    results = {
        D.TECNICA: res(f("H1", "Sin tests", A, B)),
        D.OPERATIVA: res(f("H1", "Tests lentos", M, B)),
    }
    assert structural_findings(results) == []


def test_structural_result_independent_of_agent_completion_order():
    a = {
        D.COMERCIAL: res(f("H1", "Sin analítica web instalada", A, B)),
        D.MARKETING: res(f("H2", "Analítica web no instalada", A, B)),
    }
    b = dict(reversed(list(a.items())))
    sa, sb = structural_findings(a), structural_findings(b)
    assert [s.label for s in sa] == [s.label for s in sb]
    assert [s.entries for s in sa] == [s.entries for s in sb]
