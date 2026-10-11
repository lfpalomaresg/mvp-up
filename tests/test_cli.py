import json
import re

import pytest

from mvpup.cli import main
from mvpup.parsing import GROUP_SEPARATOR
from support import LIGERA_OUTPUT, VALID_OUTPUT

BASE = ["--product", "Producto Demo", "--stage", "mvp", "--objective", "ingresos"]


def test_plan_prints_selection_batches_and_cost(capsys):
    assert main(["plan", *BASE]) == 0
    out = capsys.readouterr().out
    assert "Modo: express" in out and "250-400k" in out
    assert "comercial+marketing" in out


def test_plan_full_without_confirmation_fails(capsys):
    assert main(["plan", *BASE, "--mode", "full"]) == 2
    assert "confirmación" in capsys.readouterr().err


def test_plan_show_prompts(capsys):
    main(["plan", *BASE, "--show-prompts"])
    assert "## Score: X/10 (rúbrica al pie)" in capsys.readouterr().out


def test_invalid_dimension_argument_exits():
    with pytest.raises(SystemExit):
        main(["plan", *BASE, "--add", "astrologia"])


def test_run_with_fake_runner_writes_report(tmp_path, capsys):
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    responses = tmp_path / "resp.json"
    responses.write_text(json.dumps({"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                     "comercial+marketing": grouped}), encoding="utf-8")
    code = main(["run", *BASE, "--runner", "fake", "--fake-responses", str(responses),
                 "--out", str(tmp_path / "informes")])
    assert code == 0
    out = capsys.readouterr().out
    assert "Informe:" in out and "TOP-5" in out
    reports = list((tmp_path / "informes" / "producto-demo").glob("*-informe.md"))
    assert len(reports) == 1


def test_run_with_forbidden_model_fails_before_any_call(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["run", *BASE, "--model", "claude-fable-5-1", "--out", str(tmp_path)]) == 2
    assert "prohibido" in capsys.readouterr().err
    assert not any(tmp_path.rglob("*-informe.md"))


def test_validate_ok_and_invalid(tmp_path, capsys):
    good = tmp_path / "ok.md"
    good.write_text(VALID_OUTPUT, encoding="utf-8")
    assert main(["validate", str(good), "--dims", "tecnica"]) == 0
    bad = tmp_path / "bad.md"
    bad.write_text("nada", encoding="utf-8")
    assert main(["validate", str(bad), "--dims", "tecnica"]) == 2
    lig = tmp_path / "lig.md"
    lig.write_text(LIGERA_OUTPUT, encoding="utf-8")
    assert main(["validate", str(lig), "--ligera"]) == 0
    assert "FORMATO INVÁLIDO" in capsys.readouterr().err



def test_cli_cartera(cartera, capsys):
    assert main(["cartera", "--out", str(cartera)]) == 0
    assert "Síntesis de cartera" in capsys.readouterr().out
    assert main(["cartera", "--out", str(cartera), "--save"]) == 0
    assert (cartera / "_cartera.md").is_file()


def test_cli_cartera_missing_dir(tmp_path, capsys):
    assert main(["cartera", "--out", str(tmp_path / "nada")]) == 2


def _write_resp(tmp_path, mapping):
    p = tmp_path / "resp.json"
    p.write_text(json.dumps(mapping), encoding="utf-8")
    return str(p)


def test_run_with_nothing_evaluated_exits_nonzero(tmp_path, capsys):
    resp = _write_resp(tmp_path, {"*": "basura"})
    code = main(["run", *BASE, "--runner", "fake", "--fake-responses", resp,
                 "--out", str(tmp_path / "informes")])
    assert code == 3
    assert "ninguna dimensión" in capsys.readouterr().err


def test_anthropic_runner_without_key_fails_fast(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["run", *BASE, "--out", str(tmp_path / "informes")]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not (tmp_path / "informes").exists()


def test_out_inside_git_repo_must_be_ignored(tmp_path, capsys):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    resp = _write_resp(tmp_path, {"*": VALID_OUTPUT})
    code = main(["run", *BASE, "--runner", "fake", "--fake-responses", resp, "--out", str(tmp_path / "versionado")])
    assert code == 2
    assert "gitignore" in capsys.readouterr().err
    (tmp_path / ".gitignore").write_text("informes/\n", encoding="utf-8")
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    resp = _write_resp(tmp_path, {"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                  "comercial+marketing": grouped})
    assert main(["run", *BASE, "--runner", "fake", "--fake-responses", resp,
                 "--out", str(tmp_path / "informes")]) == 0


@pytest.mark.parametrize("args", [
    ["validate", "/no/existe.md", "--dims", "tecnica"],
    ["run", *BASE, "--runner", "fake", "--fake-responses", "/no/existe.json"],
])
def test_expected_io_errors_exit_2_without_traceback(args, capsys):
    assert main(args) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err and "Error" in err


def test_invalid_fake_responses_json_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{no", encoding="utf-8")
    assert main(["run", *BASE, "--runner", "fake", "--fake-responses", str(bad)]) == 2


def test_agent_exception_text_is_redacted_in_log(tmp_path):
    from mvpup.dimensions import Objective, Stage
    from mvpup.intake import Intake
    from mvpup.orchestrator import run_pass
    from mvpup.runners import FakeRunner

    url = "https://usuario:" + "clave" + "ficticia@proxy.example.invalid"

    def boom(prompt):
        raise RuntimeError(f"fallo de conexión vía {url}")

    result = run_pass(Intake(product="Demo", stage=Stage.MVP, objective=Objective.INGRESOS),
                      FakeRunner({"*": boom}))
    joined = "\n".join(result.log)
    assert "clavefidticia" not in joined and ("clave" + "ficticia") not in joined
    assert "[REDACTADO]" in joined


def test_out_check_fails_closed_when_git_errors(tmp_path, monkeypatch):
    import subprocess

    from mvpup import cli

    def boom(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=30)

    monkeypatch.setattr(cli.subprocess, "run", boom)
    with pytest.raises(cli.CliError, match="no se pudo comprobar"):
        cli.check_out_dir(tmp_path / "informes")


def test_out_check_without_git_binary_is_allowed(tmp_path, monkeypatch):
    from mvpup import cli

    def missing(*a, **kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(cli.subprocess, "run", missing)
    cli.check_out_dir(tmp_path / "informes")  # sin git no se puede versionar nada


def test_out_check_outside_repo_with_spanish_locale(tmp_path, monkeypatch):
    from mvpup import cli

    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    cli.check_out_dir(tmp_path / "informes")  # tmp_path no es un repo: debe pasar


# --- dry-run: pasada completa con datos sintéticos, sin red ni API key ---

def _block_network(monkeypatch):
    import socket

    def no_socket(*a, **kw):
        raise AssertionError("el dry-run no debe abrir conexiones de red")

    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _never(*a, **kw):
    raise AssertionError("el dry-run no debe construir ningún runner real")


def test_dry_run_end_to_end_writes_a_complete_report(tmp_path, capsys, monkeypatch):
    from mvpup import cli
    from support import template_headers

    _block_network(monkeypatch)
    monkeypatch.setattr(cli, "_runner", _never)
    out = tmp_path / "informes"
    assert main(["run", *BASE, "--dry-run", "--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert "DRY-RUN" in captured.err and "Lote 1:" in captured.err
    assert "Informe:" in captured.out and "Score global:" in captured.out and "TOP-5" in captured.out

    paths = list((out / "producto-demo").glob("*-dry-run.md"))
    assert len(paths) == 1 and not list((out / "producto-demo").glob("*-informe.md"))
    md = paths[0].read_text(encoding="utf-8")
    lines = [ln.strip() for ln in md.splitlines()]
    positions = [lines.index(h) for h in template_headers()]
    assert positions == sorted(positions)
    assert "DRY-RUN" in md and "[sintético]" in md
    # las cuatro dimensiones de la etapa mvp evaluadas, ninguna «sin evaluar»
    for label in ("Técnica", "Producto / UX", "Comercial", "Marketing y hype"):
        assert f"| {label} | " in md
    assert "sin evaluar" not in md
    # matriz con los cuatro cuadrantes poblados y un hallazgo estructural
    for cell in ("⚡ QUICK WINS: —", "🎯 APUESTAS: —", "📋 Si sobra tiempo: —", "🗑️ Descartar: —"):
        assert cell not in md
    assert "Ninguno detectado" not in md and "bloquea:" in md
    assert "Primera pasada" in md
    assert re.search(r"^5\. ", md, re.MULTILINE)  # TOP-5 completo
    data = json.loads(paths[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert data["dry_run"] is True and data["unevaluated"] == []


@pytest.mark.parametrize("extra", [
    ["--stage", "idea"], ["--stage", "produccion"], ["--stage", "facturando"],
    ["--mode", "full", "--confirm-full"], ["--mode", "ligera"],
    ["--no-software", "--no-customer-data", "--stage", "facturando"],
])
def test_dry_run_covers_every_stage_and_mode(tmp_path, capsys, monkeypatch, extra):
    _block_network(monkeypatch)
    args = ["run", "--product", "Demo", "--objective", "vendible", "--stage", "mvp", *extra]
    assert main([*args, "--dry-run", "--out", str(tmp_path / "informes")]) == 0
    md = next((tmp_path / "informes" / "demo").glob("*-dry-run.md")).read_text(encoding="utf-8")
    assert "sin evaluar" not in md and "DRY-RUN" in md


def test_dry_run_is_incompatible_with_fake_runner_and_anchor(tmp_path, capsys):
    resp = _write_resp(tmp_path, {"*": VALID_OUTPUT})
    assert main(["run", *BASE, "--dry-run", "--runner", "fake", "--fake-responses", resp,
                 "--out", str(tmp_path / "i")]) == 2
    assert "--dry-run" in capsys.readouterr().err
    assert main(["run", *BASE, "--dry-run", "--anclar", "--ficha", str(tmp_path / "f.md"),
                 "--out", str(tmp_path / "i")]) == 2
    assert "--anclar" in capsys.readouterr().err
    assert not (tmp_path / "f.md").exists() and not (tmp_path / "i").exists()


# --- loop 3: --timeout se valida antes de lanzar la pasada ---

@pytest.mark.parametrize("value", ["0", "-5", "nan", "abc"])
def test_non_positive_timeout_is_a_usage_error_before_the_pass(tmp_path, capsys, value):
    with pytest.raises(SystemExit) as exc:
        main(["run", *BASE, "--dry-run", "--timeout", value, "--out", str(tmp_path / "inf")])
    assert exc.value.code == 2
    assert "--timeout" in capsys.readouterr().err
    assert not (tmp_path / "inf").exists()


# --- loop 4: coste orientativo con un plan vacío ---

def test_cost_hint_with_no_agents_says_so_instead_of_zero_tokens(capsys):
    from mvpup.cli import cost_hint
    from mvpup.dimensions import Mode

    assert "0-0k" not in cost_hint(Mode.EXPRESS, 0)
    assert "sin agentes" in cost_hint(Mode.LIGERA, 0)
    main(["plan", *BASE, "--remove", "tecnica,producto_ux,comercial,marketing"])
    out = capsys.readouterr().out
    assert "sin agentes" in out and "0-0k" not in out


# --- loop 6: --fake-responses con valores no textuales → código 2 con la clave culpable ---

def test_fake_responses_with_non_text_value_is_a_usage_error(tmp_path, capsys):
    resp = _write_resp(tmp_path, {"tecnica": 5, "producto_ux": VALID_OUTPUT})
    assert main(["run", *BASE, "--runner", "fake", "--fake-responses", resp, "--out", str(tmp_path / "inf")]) == 2
    err = capsys.readouterr().err
    assert "tecnica" in err and "Traceback" not in err
    assert not (tmp_path / "inf").exists()


# --- loop 7: Ctrl-C durante la pasada sale limpio con código 130 ---

def test_keyboard_interrupt_during_the_pass_exits_130_without_traceback(tmp_path, capsys, monkeypatch):
    from mvpup import orchestrator

    def interrupted(*a, **kw):
        raise KeyboardInterrupt

    monkeypatch.setattr(orchestrator, "run_pass", interrupted)
    assert main(["run", *BASE, "--dry-run", "--out", str(tmp_path / "inf")]) == 130
    err = capsys.readouterr().err
    assert "Interrumpido" in err and "Traceback" not in err
