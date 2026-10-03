"""Loop 10: hallazgos del audit global (Gemini). Datos ficticios."""

from datetime import date

import pytest

from mvpup.dimensions import Dimension as D
from mvpup.dimensions import Mode, Objective, Stage
from mvpup.intake import Intake
from mvpup.parsing import GROUP_SEPARATOR, FormatError, parse_agent_output, parse_grouped_output
from support import VALID_OUTPUT


# (4) impacto/esfuerzo en palabra completa y hallazgos ilegibles
def test_full_words_for_impact_and_effort_are_accepted():
    text = VALID_OUTPUT.replace("Impacto: A · Esfuerzo: B", "Impacto: Alto · Esfuerzo: Bajo")
    assert parse_agent_output(text).findings[0].impact.value == "A"


def test_unparseable_finding_line_triggers_retry():
    text = VALID_OUTPUT.replace("· Impacto: M · Esfuerzo: B · Evidencia: requirements",
                                "· Impacto: ??? · Evidencia: requirements")
    with pytest.raises(FormatError, match="ilegible"):
        parse_agent_output(text)


# (5) separador agrupado tolerante a mayúsculas y tildes
@pytest.mark.parametrize("sep", ["Comercial", "COMERCIAL", "comercial "])
def test_grouped_separator_is_case_and_accent_insensitive(sep):
    text = f"{GROUP_SEPARATOR}{sep}\n{VALID_OUTPUT}\n{GROUP_SEPARATOR}Marketing\n{VALID_OUTPUT}"
    assert set(parse_grouped_output(text, (D.COMERCIAL, D.MARKETING))) == {D.COMERCIAL, D.MARKETING}


def test_grouped_separator_accepts_accented_label():
    text = f"{GROUP_SEPARATOR}Técnica\n{VALID_OUTPUT}\n{GROUP_SEPARATOR}Seguridad\n{VALID_OUTPUT}"
    assert set(parse_grouped_output(text, (D.TECNICA, D.SEGURIDAD))) == {D.TECNICA, D.SEGURIDAD}


# (3) modelos por dimensión en pasadas full críticas
def test_critical_full_pass_uses_opus_for_economica_and_comercial():
    from mvpup.cli import critical_models

    full = Intake(product="Demo", stage=Stage.FACTURANDO, objective=Objective.VENDIBLE,
                  mode=Mode.FULL, full_confirmed=True)
    assert critical_models(full) == {"economica": "claude-opus-5-5", "comercial": "claude-opus-5-5"}
    express = Intake(product="Demo", stage=Stage.FACTURANDO, objective=Objective.VENDIBLE)
    assert critical_models(express) == {}
    ingresos = Intake(product="Demo", stage=Stage.FACTURANDO, objective=Objective.INGRESOS,
                      mode=Mode.FULL, full_confirmed=True)
    assert critical_models(ingresos) == {}


def test_runner_uses_model_override_per_task_key():
    from types import SimpleNamespace

    from mvpup.anthropic_runner import AnthropicRunner

    calls = []

    def create(**kw):
        calls.append(kw["model"])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    r = AnthropicRunner(client=client, model_by_key={"economica": "claude-opus-5-5"})
    r.run("p", task_key="economica")
    r.run("p", task_key="legal")
    assert calls == ["claude-opus-5-5", r.model]


def test_model_overrides_respect_policy():
    from mvpup.anthropic_runner import AnthropicRunner
    from mvpup.config import ModelPolicyError

    with pytest.raises(ModelPolicyError):
        AnthropicRunner(client=object(), model_by_key={"economica": "claude-fable-5-1"})


# (6) coste orientativo según nº real de agentes
def test_cost_hint_scales_with_agents(capsys):
    from mvpup.cli import main

    base = ["--product", "Demo", "--stage", "mvp", "--objective", "ingresos"]
    main(["plan", *base, "--add", ",".join(d.value for d in D)])
    out = capsys.readouterr().out
    assert "6 agentes" in out


# (2) anclaje «LEER AL RETOMAR» en la ficha (opt-in)
def test_anchor_is_appended_once(tmp_path):
    from mvpup.report import anchor_ficha

    ficha = tmp_path / "demo.md"
    ficha.write_text("# Demo\nFicha ficticia.\n", encoding="utf-8")
    report_path = tmp_path / "informes" / "demo" / "2026-10-04-informe.md"
    anchor_ficha(ficha, report_path, 6.2, date(2026, 10, 4))
    anchor_ficha(ficha, report_path, 6.2, date(2026, 10, 4))
    text = ficha.read_text(encoding="utf-8")
    assert text.count("## ⚡ MVP-UP 6,2/10 (2026-10-04) — LEER AL RETOMAR") == 1
    assert "2026-10-04-informe.md" in text


def test_anchor_creates_minimal_ficha_if_missing(tmp_path):
    from mvpup.report import anchor_ficha

    ficha = tmp_path / "nueva.md"
    anchor_ficha(ficha, tmp_path / "x-informe.md", None, date(2026, 10, 4), product="Nueva Demo")
    text = ficha.read_text(encoding="utf-8")
    assert text.startswith("# Nueva Demo") and "LEER AL RETOMAR" in text and "—/10" in text


def test_cli_anclar_requires_ficha_and_writes_anchor(tmp_path, capsys):
    import json

    from mvpup.cli import main

    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    resp = tmp_path / "resp.json"
    resp.write_text(json.dumps({"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                "comercial+marketing": grouped}), encoding="utf-8")
    base = ["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos",
            "--runner", "fake", "--fake-responses", str(resp), "--out", str(tmp_path / "inf")]
    assert main([*base, "--anclar"]) == 2
    ficha = tmp_path / "fichas" / "demo.md"
    assert main([*base, "--anclar", "--ficha", str(ficha)]) == 0
    assert "LEER AL RETOMAR" in ficha.read_text(encoding="utf-8")


def test_anclar_without_ficha_fails_before_any_agent_runs(tmp_path):
    import json

    from mvpup.cli import main

    resp = tmp_path / "resp.json"
    resp.write_text(json.dumps({"*": "nunca debería llamarse"}), encoding="utf-8")
    code = main(["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos",
                 "--runner", "fake", "--fake-responses", str(resp), "--out", str(tmp_path / "inf"),
                 "--anclar"])
    assert code == 2
    assert not (tmp_path / "inf").exists()  # no se lanzó la pasada


def test_minimal_ficha_includes_repo(tmp_path):
    from mvpup.report import anchor_ficha

    ficha = tmp_path / "nueva.md"
    anchor_ficha(ficha, tmp_path / "x-informe.md", 5.0, date(2026, 10, 4), product="Demo",
                 repo="../demo-repo")
    assert "- Repo: `../demo-repo`" in ficha.read_text(encoding="utf-8")


def test_second_pass_same_day_gets_its_own_anchor(tmp_path, capsys):
    import json

    from mvpup.cli import main

    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    resp = tmp_path / "resp.json"
    resp.write_text(json.dumps({"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                "comercial+marketing": grouped}), encoding="utf-8")
    ficha = tmp_path / "demo.md"
    base = ["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos", "--runner", "fake",
            "--fake-responses", str(resp), "--out", str(tmp_path / "inf"), "--ficha", str(ficha), "--anclar"]
    main(base)
    capsys.readouterr()
    main(base)  # segunda pasada el mismo día → informe-2: SÍ debe anclarse
    out = capsys.readouterr().out
    assert "añadido" in out
    text = ficha.read_text(encoding="utf-8")
    assert "2026" in text and "-informe-2.md" in text and text.count("LEER AL RETOMAR") == 2


def test_same_report_anchor_is_idempotent_even_with_other_score(tmp_path):
    from mvpup.report import anchor_ficha

    ficha = tmp_path / "demo.md"
    report = tmp_path / "2026-10-04-informe.md"
    assert anchor_ficha(ficha, report, 5.0, date(2026, 10, 4)) is True
    assert anchor_ficha(ficha, report, 5.0, date(2026, 10, 4)) is False
