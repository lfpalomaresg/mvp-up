"""Loops de automejora de la ronda 2 (cada uno con su test en rojo previo). Datos ficticios."""

import json

import pytest

from mvpup.cli import main
from mvpup.parsing import GROUP_SEPARATOR
from support import VALID_OUTPUT

BASE = ["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos"]


def _responses(tmp_path):
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    resp = tmp_path / "resp.json"
    resp.write_text(json.dumps({"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                "comercial+marketing": grouped}), encoding="utf-8")
    return str(resp)


def _never(*a, **kw):
    raise AssertionError("no debe construirse ningún runner")


# --- loop 1: --fake-responses sin --runner fake se ignoraba y habría lanzado agentes reales ---

def test_fake_responses_without_fake_runner_is_a_usage_error_before_any_runner(tmp_path, capsys, monkeypatch):
    from mvpup import cli

    monkeypatch.setattr(cli, "_runner", _never)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-ficticia-de-test")
    code = main([*BASE, "--fake-responses", _responses(tmp_path), "--out", str(tmp_path / "inf")])
    assert code == 2
    err = capsys.readouterr().err
    assert "--runner fake" in err and "Traceback" not in err
    assert not (tmp_path / "inf").exists()


# --- loop 2: errores de uso lanzados como SystemExit(msg) salían con código 1, no 2 ---

def test_validate_without_dims_is_a_usage_error_with_exit_2(tmp_path, capsys):
    good = tmp_path / "ok.md"
    good.write_text(VALID_OUTPUT, encoding="utf-8")
    assert main(["validate", str(good)]) == 2
    err = capsys.readouterr().err
    assert "--dims" in err and err.startswith("Error:")


def test_fake_runner_without_responses_is_a_usage_error_with_exit_2(tmp_path, capsys):
    assert main([*BASE, "--runner", "fake", "--out", str(tmp_path / "inf")]) == 2
    err = capsys.readouterr().err
    assert "--fake-responses" in err and err.startswith("Error:")
    assert not (tmp_path / "inf").exists()


# --- loop 3: una pasada sin ninguna dimensión evaluada (código 3) anclaba igualmente la ficha ---

def test_pass_with_nothing_evaluated_leaves_the_ficha_untouched(tmp_path, capsys):
    resp = tmp_path / "basura.json"
    resp.write_text(json.dumps({"*": "basura"}), encoding="utf-8")
    ficha = tmp_path / "demo.md"
    original = "# Demo\n\nFicha ficticia.\n"
    ficha.write_text(original, encoding="utf-8")
    code = main([*BASE, "--runner", "fake", "--fake-responses", str(resp), "--out", str(tmp_path / "inf"),
                 "--ficha", str(ficha), "--anclar"])
    assert code == 3
    assert ficha.read_text(encoding="utf-8") == original
    assert "no se ancla" in capsys.readouterr().err
    missing = tmp_path / "nueva.md"
    code = main([*BASE, "--runner", "fake", "--fake-responses", str(resp), "--out", str(tmp_path / "inf"),
                 "--ficha", str(missing), "--anclar"])
    assert code == 3 and not missing.exists()


# --- loop 5: tres formateadores de score distintos; la Evolución decía «6/10» y la cabecera «6,0/10» ---

def test_previous_global_score_in_evolution_uses_the_same_format_as_the_header():
    from datetime import date

    from mvpup import compare, portfolio, report, scoring
    from mvpup.compare import compare_with_previous
    from mvpup.dimensions import Objective, Stage
    from mvpup.intake import Intake
    from mvpup.orchestrator import run_pass
    from mvpup.report import build_report
    from mvpup.runners import FakeRunner

    assert scoring.fmt_score(6.0, 1) == "6,0" and scoring.fmt_score(6.25) == "6,2" and scoring.fmt_score(None) == "—"
    assert report.fmt_score is scoring.fmt_score  # un único formateador para informe, comparación y cartera
    assert compare.fmt_score is scoring.fmt_score and portfolio.fmt_score is scoring.fmt_score
    intake = Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS)
    rep = build_report(run_pass(intake, FakeRunner({"*": VALID_OUTPUT})), today=date(2026, 10, 4))
    compare_with_previous(rep, {"schema": 1, "date": "2026-09-01", "objective": "ingresos", "global_score": 6.0,
                                "scores": {"tecnica": 6}})
    assert "score global 6,0/10" in rep.evolution[0]
