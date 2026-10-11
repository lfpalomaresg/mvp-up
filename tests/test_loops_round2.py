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
