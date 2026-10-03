from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Objective
from mvpup.scoring import global_score, status_icon


def test_weighted_mean_doubles_priority_dimensions():
    # ingresos → comercial ×2; técnica ×1 → (8*2 + 5) / 3 = 7.0
    scores = {D.COMERCIAL: 8, D.TECNICA: 5}
    assert global_score(scores, Objective.INGRESOS) == 7.0
    # vendible → técnica ×2 → (8 + 5*2) / 3 = 6.0
    assert global_score(scores, Objective.VENDIBLE) == 6.0


def test_unevaluated_dimensions_are_ignored():
    assert global_score({D.COMERCIAL: 6, D.LEGAL: None}, Objective.INGRESOS) == 6.0
    assert global_score({D.LEGAL: None}, Objective.INGRESOS) is None


def test_status_icons():
    assert [status_icon(s) for s in (9, 7, 6, 5, 4.9, None)] == ["🟢", "🟢", "🟡", "🟡", "🔴", "⚪"]
