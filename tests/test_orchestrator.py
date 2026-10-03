import threading

import pytest

from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.parsing import GROUP_SEPARATOR
from mvpup.runners import FakeRunner


def intake(**kw):
    base = dict(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    base.update(kw)
    return Intake(**base)


def grouped(*pairs):
    return "\n".join(f"{GROUP_SEPARATOR}{d.value}\n{text}" for d, text in pairs)


def test_express_pass_collects_one_result_per_dimension(valid_output):
    runner = FakeRunner({
        "tecnica": valid_output,
        "producto_ux": valid_output.replace("6/10", "7/10"),
        "comercial+marketing": grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output)),
    })
    result = run_pass(intake(), runner)
    assert set(result.results) == {D.TECNICA, D.PRODUCTO_UX, D.COMERCIAL, D.MARKETING}
    assert result.results[D.PRODUCTO_UX].score == 7
    assert result.unevaluated == ()
    assert len(runner.calls) == 3


def test_invalid_format_is_retried_once_with_reinforced_prompt(valid_output):
    runner = FakeRunner({
        "tecnica": ["basura sin headers", valid_output],
        "producto_ux": valid_output,
        "comercial+marketing": grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output)),
    })
    result = run_pass(intake(), runner)
    assert result.results[D.TECNICA].score == 6
    retry_prompt = [p for k, p in runner.calls if k == "tecnica"][1]
    assert "no cumplía el formato" in retry_prompt
    assert any("tecnica" in log and "reintento" in log for log in result.log)


def test_second_failure_marks_dimension_unevaluated_and_pass_continues(valid_output):
    runner = FakeRunner({
        "tecnica": ["basura", "más basura", valid_output],
        "producto_ux": valid_output,
        "comercial+marketing": grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output)),
    })
    result = run_pass(intake(), runner)
    assert D.TECNICA not in result.results
    assert result.unevaluated == (D.TECNICA,)
    assert len([k for k, _ in runner.calls if k == "tecnica"]) == 2


def test_runner_exception_counts_as_failure(valid_output):
    def boom(prompt):
        raise RuntimeError("red caída")

    runner = FakeRunner({
        "tecnica": [boom, valid_output],
        "producto_ux": valid_output,
        "comercial+marketing": grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output)),
    })
    result = run_pass(intake(), runner)
    assert result.results[D.TECNICA].score == 6
    assert any("red caída" in log for log in result.log)


def test_grouped_failure_marks_both_dimensions_unevaluated(valid_output):
    runner = FakeRunner({
        "tecnica": valid_output,
        "producto_ux": valid_output,
        "comercial+marketing": ["x", "y"],
    })
    result = run_pass(intake(), runner)
    assert set(result.unevaluated) == {D.COMERCIAL, D.MARKETING}


def test_full_mode_never_exceeds_five_concurrent_agents(valid_output):
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}
    gate = threading.Barrier(5, timeout=2)

    def tracked(prompt):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        try:
            gate.wait()
        except threading.BrokenBarrierError:
            pass
        with lock:
            state["now"] -= 1
        return valid_output

    runner = FakeRunner({d.value: tracked for d in D})
    result = run_pass(intake(mode=Mode.FULL, full_confirmed=True), runner)
    assert len(result.results) == 10
    assert state["peak"] == 5


def test_not_applicable_dimensions_are_reported_and_not_run(valid_output):
    runner = FakeRunner({d.value: valid_output for d in D})
    result = run_pass(
        intake(mode=Mode.FULL, full_confirmed=True, has_software=False, has_customer_data=False),
        runner,
    )
    assert set(result.not_applicable) == {D.TECNICA, D.SEGURIDAD}
    assert {k for k, _ in runner.calls}.isdisjoint({"tecnica", "seguridad"})


def test_ligera_pass_uses_ligera_parser():
    from support import LIGERA_OUTPUT

    runner = FakeRunner({"*": LIGERA_OUTPUT})
    result = run_pass(intake(mode=Mode.LIGERA), runner)
    assert result.ligera is not None and result.ligera.score == 4
    assert result.results == {}


def test_fake_runner_without_response_raises():
    with pytest.raises(KeyError):
        FakeRunner({}).run("prompt", task_key="nada")


def test_grouped_agent_salvages_valid_block_when_other_fails(valid_output):
    good_comercial_bad_marketing = grouped((D.COMERCIAL, valid_output), (D.MARKETING, "roto"))
    runner = FakeRunner({
        "tecnica": valid_output,
        "producto_ux": valid_output,
        "comercial+marketing": good_comercial_bad_marketing,
    })
    result = run_pass(intake(), runner)
    assert result.results[D.COMERCIAL].score == 6
    assert result.unevaluated == (D.MARKETING,)


def test_grouped_retry_completes_missing_dimension(valid_output):
    first = grouped((D.COMERCIAL, valid_output), (D.MARKETING, "roto"))
    second = grouped((D.COMERCIAL, "roto"), (D.MARKETING, valid_output.replace("6/10", "3/10")))
    runner = FakeRunner({
        "tecnica": valid_output,
        "producto_ux": valid_output,
        "comercial+marketing": [first, second],
    })
    result = run_pass(intake(), runner)
    assert result.results[D.COMERCIAL].score == 6  # se conserva el del 1er intento
    assert result.results[D.MARKETING].score == 3
    assert result.unevaluated == ()


def test_hung_agent_times_out_and_pass_continues(valid_output):
    import time

    release = threading.Event()

    def hang(prompt):
        release.wait(5)
        return valid_output

    runner = FakeRunner({
        "tecnica": hang,
        "producto_ux": valid_output,
        "comercial+marketing": grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output)),
    })
    start = time.monotonic()
    result = run_pass(intake(), runner, agent_timeout=0.05)
    release.set()
    assert time.monotonic() - start < 2
    assert result.unevaluated == (D.TECNICA,)
    assert any("TimeoutError" in log for log in result.log)


def test_hung_agents_never_exceed_five_live_calls(valid_output):
    lock = threading.Lock()
    state = {"live": 0, "peak": 0}
    release = threading.Event()

    def hang(prompt):
        with lock:
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
        release.wait(5)
        with lock:
            state["live"] -= 1
        return valid_output

    runner = FakeRunner({d.value: hang for d in D})
    result = run_pass(intake(mode=Mode.FULL, full_confirmed=True), runner, agent_timeout=0.05)
    peak = state["peak"]
    release.set()
    assert peak <= 5
    assert len(result.unevaluated) == 10


def test_extra_unrequested_block_is_logged_not_retried(valid_output):
    text = grouped((D.COMERCIAL, valid_output), (D.MARKETING, valid_output), (D.LEGAL, valid_output))
    runner = FakeRunner({"tecnica": valid_output, "producto_ux": valid_output, "comercial+marketing": text})
    result = run_pass(intake(), runner)
    assert result.unevaluated == ()
    assert len([k for k, _ in runner.calls if k == "comercial+marketing"]) == 1
    assert any("bloque no pedido: legal" in log for log in result.log)
