"""Consumo de tokens por agente (solo tokens, nunca importes). Cliente falso: sin red ni API key."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from mvpup.anthropic_runner import AgentRefusedError, AnthropicRunner, TruncatedOutputError
from mvpup.cli import main
from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.orchestrator import run_pass
from mvpup.report import build_report, render_markdown, to_json
from mvpup.runners import AgentUsage, FakeRunner
from support import LIGERA_OUTPUT, VALID_OUTPUT

TODAY = date(2026, 10, 12)


class Messages:
    """`messages.create` falso: devuelve `usage` como la API (o lo que se le configure)."""

    def __init__(self, texts=None, usage="default", stop_reason="end_turn"):
        self.texts, self.usage, self.stop_reason, self.calls = texts or {}, usage, stop_reason, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        n = 2 if "opus" in kwargs["model"] else 1  # determinista aunque los agentes corran en hilos
        usage = SimpleNamespace(input_tokens=1000 * n, output_tokens=100 * n) if self.usage == "default" else self.usage
        response = SimpleNamespace(
            stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=VALID_OUTPUT)])
        if usage is not None:
            response.usage = usage
        return response


def runner(**kw):
    messages = Messages(**kw)
    return AnthropicRunner(client=SimpleNamespace(messages=messages), model="claude-sonnet-5-5",
                           model_by_key={"comercial": "claude-opus-5-5"}), messages


def test_runner_records_tokens_and_model_per_agent():
    r, _ = runner()
    r.run("p", task_key="tecnica")
    r.run("p", task_key="comercial")
    assert r.usage() == {
        "tecnica": AgentUsage(model="claude-sonnet-5-5", input_tokens=1000, output_tokens=100, calls=1),
        "comercial": AgentUsage(model="claude-opus-5-5", input_tokens=2000, output_tokens=200, calls=1),
    }


def test_retries_of_the_same_agent_accumulate():
    r, _ = runner()
    r.run("p", task_key="tecnica")
    r.run("p reforzado", task_key="tecnica")
    assert r.usage()["tecnica"] == AgentUsage("claude-sonnet-5-5", input_tokens=2000, output_tokens=200, calls=2)


@pytest.mark.parametrize("stop, exc", [("refusal", AgentRefusedError), ("max_tokens", TruncatedOutputError)])
def test_tokens_of_a_failed_call_are_still_counted(stop, exc):
    """Una llamada rechazada o truncada también se pagó: el consumo no puede salir a cero."""
    r, _ = runner(stop_reason=stop)
    with pytest.raises(exc):
        r.run("p", task_key="tecnica")
    assert r.usage()["tecnica"] == AgentUsage("claude-sonnet-5-5", input_tokens=1000, output_tokens=100, calls=1)


def test_cache_tokens_count_as_input():
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_creation_input_tokens=300, cache_read_input_tokens=4000)
    r, _ = runner(usage=usage)
    r.run("p", task_key="tecnica")
    assert r.usage()["tecnica"].input_tokens == 4310


@pytest.mark.parametrize("usage", [
    None,  # respuesta sin `usage`
    SimpleNamespace(),  # `usage` sin campos
    SimpleNamespace(input_tokens=None, output_tokens="muchos"),  # tipos inesperados
])
def test_missing_or_odd_usage_never_breaks_the_call(usage):
    r, _ = runner(usage=usage)
    assert r.run("p", task_key="tecnica") == VALID_OUTPUT
    assert r.usage()["tecnica"] == AgentUsage("claude-sonnet-5-5", input_tokens=0, output_tokens=0, calls=1)


def test_usage_returns_a_copy():
    r, _ = runner()
    r.run("p", task_key="tecnica")
    r.usage().clear()
    assert "tecnica" in r.usage()


def _intake(**kw):
    return Intake(product="Producto Demo", stage=Stage.MVP, objective=Objective.INGRESOS,
                  remove={"producto_ux", "marketing"}, **kw)


def test_pass_result_and_report_carry_the_usage():
    r, messages = runner()
    result = run_pass(_intake(), r)
    assert len(messages.calls) == 2 and set(result.usage) == {"tecnica", "comercial"}
    data = to_json(build_report(result, today=TODAY))
    assert data["usage"] == {
        "agents": {
            "tecnica": {"model": "claude-sonnet-5-5", "input_tokens": 1000, "output_tokens": 100, "calls": 1},
            "comercial": {"model": "claude-opus-5-5", "input_tokens": 2000, "output_tokens": 200, "calls": 1},
        },
        "total": {"input_tokens": 3000, "output_tokens": 300, "calls": 2},
        "models": ["claude-opus-5-5", "claude-sonnet-5-5"],
    }
    json.dumps(data)  # serializable
    assert list(data["usage"]["agents"]) == ["tecnica", "comercial"]  # orden del plan, no de llegada


def test_usage_order_follows_the_plan_not_thread_completion():
    from mvpup.report import usage_summary

    result = run_pass(_intake(), FakeRunner({"*": VALID_OUTPUT}))
    result.usage = {  # como si «comercial» hubiera terminado antes que «tecnica»
        "comercial": AgentUsage("claude-sonnet-5-5", 2, 1, 1),
        "tecnica": AgentUsage("claude-sonnet-5-5", 4, 3, 1),
    }
    summary = usage_summary(result)
    assert summary is not None and list(summary["agents"]) == ["tecnica", "comercial"]


def test_markdown_has_one_usage_line_with_totals_models_and_no_money():
    r, _ = runner()
    md = render_markdown(build_report(run_pass(_intake(), r), today=TODAY))
    lines = [ln for ln in md.splitlines() if ln.startswith("**Consumo:**")]
    assert len(lines) == 1
    line = lines[0]
    assert "3.000 tokens de entrada" in line and "300 de salida" in line and "2 llamadas" in line
    assert "claude-opus-5-5" in line and "claude-sonnet-5-5" in line
    assert "tecnica 1.000/100" in line and "comercial 2.000/200" in line
    assert not any(sign in md for sign in ("€", "$", "USD"))  # solo tokens: los precios cambian


def test_fake_runner_reports_no_usage_and_nothing_breaks():
    result = run_pass(_intake(), FakeRunner({"*": VALID_OUTPUT}))
    assert result.usage == {}
    report = build_report(result, today=TODAY)
    assert to_json(report)["usage"] is None
    assert "Consumo" not in render_markdown(report)


def test_ligera_report_also_carries_the_usage():
    messages = Messages()
    messages.create = lambda **kw: SimpleNamespace(  # type: ignore[method-assign]
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text=LIGERA_OUTPUT)],
        usage=SimpleNamespace(input_tokens=70_000, output_tokens=1_500))
    r = AnthropicRunner(client=SimpleNamespace(messages=messages), model="claude-sonnet-5-5")
    intake = Intake(product="Semilla Demo", stage=Stage.IDEA, objective=Objective.INGRESOS, mode=Mode.LIGERA)
    report = build_report(run_pass(intake, r), today=TODAY)
    assert "**Consumo:** 70.000 tokens de entrada · 1.500 de salida · 1 llamada ·" in render_markdown(report)
    assert to_json(report)["usage"]["total"] == {"input_tokens": 70_000, "output_tokens": 1_500, "calls": 1}


def test_a_runner_with_a_broken_usage_report_does_not_lose_the_pass():
    class Broken(FakeRunner):
        def usage(self):
            raise RuntimeError("contador roto")

    result = run_pass(_intake(), Broken({"*": VALID_OUTPUT}))
    assert result.usage == {} and D.TECNICA in result.results
    assert any("consumo no disponible" in ln for ln in result.log)


def test_dry_run_report_has_no_usage(tmp_path, capsys):
    assert main(["run", "--dry-run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos",
                 "--out", str(tmp_path)]) == 0
    data = json.loads(next((tmp_path / "demo").glob("*.json")).read_text(encoding="utf-8"))
    assert data["usage"] is None
    assert "Consumo" not in capsys.readouterr().out
