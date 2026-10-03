import pytest

from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake, IntakeError
from mvpup.selection import build_plan


def make(**kw) -> Intake:
    base = dict(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    base.update(kw)
    return Intake(**base)


@pytest.mark.parametrize(
    "stage, expected",
    [
        (Stage.IDEA, {D.MERCADO, D.PRODUCTO_UX, D.COMERCIAL, D.ECONOMICA}),
        (Stage.MVP, {D.TECNICA, D.PRODUCTO_UX, D.COMERCIAL, D.MARKETING}),
        (Stage.PRODUCCION, {D.MARKETING, D.COMERCIAL, D.MERCADO, D.ECONOMICA}),
        (Stage.FACTURANDO, {D.ECONOMICA, D.OPERATIVA, D.SEGURIDAD, D.LEGAL, D.DATOS}),
    ],
)
def test_express_selection_by_stage(stage, expected):
    assert set(build_plan(make(stage=stage)).selected) == expected


def test_express_groups_affine_pairs_max_two():
    plan = build_plan(make(stage=Stage.MVP))
    keys = {t.key for t in plan.tasks}
    assert "comercial+marketing" in keys
    assert all(len(t.dimensions) <= 2 for t in plan.tasks)
    # 4 dimensiones → técnica, producto_ux, comercial+marketing = 3 agentes
    assert len(plan.tasks) == 3


def test_full_requires_confirmation():
    with pytest.raises(IntakeError, match="confirmación"):
        make(mode=Mode.FULL)


def test_full_is_ten_agents_in_two_batches():
    plan = build_plan(make(mode=Mode.FULL, full_confirmed=True))
    assert len(plan.tasks) == 10
    assert [len(b) for b in plan.batches] == [5, 5]


def test_service_without_software_marks_na():
    plan = build_plan(
        make(mode=Mode.FULL, full_confirmed=True, has_software=False, has_customer_data=False)
    )
    assert set(plan.not_applicable) == {D.TECNICA, D.SEGURIDAD}
    assert D.TECNICA not in plan.selected


def test_service_with_customer_data_keeps_security():
    plan = build_plan(make(mode=Mode.FULL, full_confirmed=True, has_software=False))
    assert D.SEGURIDAD in plan.selected
    assert plan.not_applicable == (D.TECNICA,)


def test_user_can_add_and_remove_dimensions():
    plan = build_plan(make(add={"legal"}, remove={"marketing"}))
    assert D.LEGAL in plan.selected and D.MARKETING not in plan.selected


def test_add_and_remove_same_dimension_is_error():
    with pytest.raises(IntakeError):
        make(add={"legal"}, remove={"legal"})


def test_ligera_is_single_agent():
    plan = build_plan(make(mode=Mode.LIGERA))
    assert len(plan.tasks) == 1


def test_string_coercion_and_invalid_values():
    assert make(stage="idea").stage is Stage.IDEA
    with pytest.raises(IntakeError, match="stage inválido"):
        make(stage="unicornio")
    with pytest.raises(IntakeError):
        make(product="  ")


@pytest.mark.parametrize("stage", list(Stage))
def test_express_never_below_three_agents(stage):
    plan = build_plan(make(stage=stage))
    assert 3 <= len(plan.tasks) <= 5


def test_user_removing_dims_below_three_agents_warns():
    plan = build_plan(make(remove={"comercial", "marketing"}))
    assert len(plan.tasks) == 2
    assert any("por debajo" in w for w in plan.warnings)


def test_user_adding_all_dims_in_express_warns():
    plan = build_plan(make(add=set(D)))
    assert len(plan.tasks) > 5
    assert any("full" in w for w in plan.warnings)


def test_default_express_has_no_warnings():
    assert build_plan(make()).warnings == ()


def test_invalid_dimension_in_add_is_intake_error():
    with pytest.raises(IntakeError, match="dimensión inválida"):
        make(add={"astrologia"})
