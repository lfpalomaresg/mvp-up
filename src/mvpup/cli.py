"""CLI: `mvpup plan | run | validate | cartera`.

- plan: muestra la selección, los agentes, avisos y el coste orientativo (sin red).
- run: ejecuta la pasada y guarda el informe versionado (MD + JSON).
- validate: valida contra la plantilla la salida de un agente lanzado a mano
  (p.ej. desde subagentes de Claude Code).
- cartera: síntesis transversal de los últimos informes de 2+ productos.

El disparo es siempre manual; el modo full exige `--confirm-full`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import ModelPolicyError, check_model
from .dimensions import Dimension, Mode, Objective, Stage
from .intake import Intake, IntakeError
from .parsing import FormatError, parse_grouped_output, parse_ligera_output
from .prompts import build_task_prompt
from .redaction import redact
from .selection import build_plan

REPORTS_ENV = "MVPUP_REPORTS_DIR"
DEFAULT_REPORTS_DIR = "informes"

# Coste orientativo medido en la calibración 2026-07 (agentes Sonnet), SKILL.md:
# ligera ≈ 60-80k · express (3-5 agentes) ≈ 250-400k · full (10) ≈ ~1M → ~60-100k/agente.
COST_HINT = {
    Mode.LIGERA: "≈ 60-80k tokens",
    Mode.EXPRESS: "≈ 250-400k tokens",
    Mode.FULL: "≈ 1M tokens (la pasada cara)",
}
TOKENS_PER_AGENT_K = (60, 100)

CRITICAL_OBJECTIVES = (Objective.VENDIBLE, Objective.INVERSION)
CRITICAL_MODEL = "claude-opus-5-5"


def cost_hint(mode: Mode, agents: int) -> str:
    """Coste orientativo; si el plan se sale de lo calibrado, se escala por agente."""
    calibrated = {Mode.LIGERA: (1, 1), Mode.EXPRESS: (3, 5), Mode.FULL: (10, 10)}[mode]
    if calibrated[0] <= agents <= calibrated[1]:
        return f"{COST_HINT[mode]} · {agents} agentes"
    lo, hi = (agents * k for k in TOKENS_PER_AGENT_K)
    return f"≈ {lo}-{hi}k tokens · {agents} agentes (fuera de lo calibrado para {mode.value})"


def critical_models(intake: Intake) -> dict[str, str]:
    """SKILL.md: full + decisión crítica (venta/inversión) → económica y comercial con Opus."""
    if intake.mode is not Mode.FULL or intake.objective not in CRITICAL_OBJECTIVES:
        return {}
    return {Dimension.ECONOMICA.value: CRITICAL_MODEL, Dimension.COMERCIAL.value: CRITICAL_MODEL}


def _dims(value: str) -> frozenset[Dimension]:
    if not value:
        return frozenset()
    try:
        return frozenset(Dimension(v.strip()) for v in value.split(",") if v.strip())
    except ValueError as exc:
        valid = ", ".join(d.value for d in Dimension)
        raise argparse.ArgumentTypeError(f"dimensión inválida (válidas: {valid})") from exc


def _add_intake_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--product", required=True, help="nombre del producto")
    p.add_argument("--stage", required=True, choices=[s.value for s in Stage])
    p.add_argument("--objective", required=True, choices=[o.value for o in Objective])
    p.add_argument("--mode", default=Mode.EXPRESS.value, choices=[m.value for m in Mode])
    p.add_argument("--confirm-full", action="store_true", help="confirma el modo full (10 agentes)")
    p.add_argument("--repo", help="ruta local del repo/carpeta del producto")
    p.add_argument("--url", help="URL desplegada")
    p.add_argument("--context", default="", help="resumen de negocio (texto)")
    p.add_argument("--ficha", help="ruta de la ficha del producto (modo ligera)")
    p.add_argument("--wip-context", default="", help="foco estratégico / carriles WIP")
    p.add_argument("--not-in-wip", action="store_true", help="producto fuera de carriles activos")
    p.add_argument("--add", type=_dims, default=frozenset(), help="dimensiones extra, separadas por comas")
    p.add_argument("--remove", type=_dims, default=frozenset(), help="dimensiones a quitar")
    p.add_argument("--no-software", action="store_true", help="servicio sin software")
    p.add_argument("--no-customer-data", action="store_true", help="sin datos de clientes")


def _intake(args: argparse.Namespace) -> Intake:
    return Intake(
        product=args.product,
        stage=args.stage,
        objective=args.objective,
        mode=args.mode,
        repo_path=args.repo,
        url=args.url,
        context=args.context,
        ficha_path=args.ficha,
        wip_context=args.wip_context,
        in_wip_lanes=not args.not_in_wip,
        has_software=not args.no_software,
        has_customer_data=not args.no_customer_data,
        add=args.add,
        remove=args.remove,
        full_confirmed=args.confirm_full,
    )


def cmd_plan(args: argparse.Namespace) -> int:
    intake = _intake(args)
    plan = build_plan(intake)
    print(f"Producto: {intake.product} · etapa {intake.stage.value} · objetivo {intake.objective.value}")
    print(f"Modo: {intake.mode.value} · coste orientativo {cost_hint(intake.mode, len(plan.tasks))}")
    for key, model in critical_models(intake).items():
        print(f"Decisión crítica: el agente {key} usará {model}")
    print("Dimensiones: " + ", ".join(d.label for d in plan.selected))
    if plan.not_applicable:
        print("N/A: " + ", ".join(d.label for d in plan.not_applicable))
    for n, batch in enumerate(plan.batches, 1):
        print(f"Lote {n}: " + " · ".join(t.key for t in batch))
    for w in plan.warnings:
        print(f"⚠️  {w}")
    if args.show_prompts:
        for task in plan.tasks:
            print(f"\n===== PROMPT {task.key} =====\n{build_task_prompt(task, intake)}")
    return 0


def _runner(args: argparse.Namespace, intake: Intake):
    if args.runner == "fake":
        from .runners import FakeRunner

        if not args.fake_responses:
            raise SystemExit("--runner fake requiere --fake-responses <json {task_key: salida}>")
        data = json.loads(Path(args.fake_responses).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--fake-responses debe ser un objeto JSON {task_key: salida}")
        return FakeRunner(data)
    from .anthropic_runner import AnthropicRunner, repo_snapshot
    from .config import API_KEY_ENV, load_dotenv

    load_dotenv(Path.cwd() / ".env")
    if not os.environ.get(API_KEY_ENV):
        raise CliError(f"falta {API_KEY_ENV}: defínela en .env (gitignoreado) o en el entorno")
    snapshot = repo_snapshot(intake.repo_path) if intake.repo_path else ""
    return AnthropicRunner(model=args.model, snapshot=snapshot, model_by_key=critical_models(intake))


class CliError(Exception):
    """Error de uso previsible: mensaje claro y código 2, sin traceback."""


def _git(probe: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # LC_ALL=C: los mensajes de git se traducen según el locale y aquí se interpretan.
    return subprocess.run(
        ["git", "-C", str(probe), *args],
        capture_output=True, text=True, timeout=30, env={**os.environ, "LC_ALL": "C"},
    )


def check_out_dir(out: Path) -> None:
    """Dentro de un repo git, la carpeta de informes debe estar gitignoreada.

    Fail-closed: si git existe pero no se puede comprobar (error, timeout), no se escribe.
    Solo se permite seguir sin comprobar cuando git no está instalado.
    """
    probe = out if out.exists() else out.parent
    while not probe.exists():
        probe = probe.parent
    try:
        inside = _git(probe, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            if "not a git repository" in inside.stderr.lower():
                return
            raise CliError(f"no se pudo comprobar si {out} está en un repo git: {inside.stderr.strip()}")
        ignored = _git(probe, "check-ignore", "-q", str(out.resolve() / "x.md"))
    except FileNotFoundError:
        return  # git no instalado: no hay repo que pueda versionar los informes
    except (OSError, subprocess.SubprocessError) as exc:
        raise CliError(f"no se pudo comprobar .gitignore para {out}: {type(exc).__name__}") from exc
    if ignored.returncode == 1:
        raise CliError(
            f"la carpeta de informes {out} está dentro de un repo git y NO está en .gitignore: "
            "los informes pueden contener datos reales. Añádela a .gitignore o usa otra carpeta."
        )
    if ignored.returncode != 0:
        raise CliError(f"no se pudo comprobar .gitignore para {out}: {ignored.stderr.strip()}")


def cmd_run(args: argparse.Namespace) -> int:
    from .orchestrator import run_pass
    from .report import anchor_ficha, build_report, save_report

    intake = _intake(args)
    if args.model:
        check_model(args.model)  # la política de modelos va antes que cualquier otra cosa
    if args.anclar and not intake.ficha_path:
        # Error de uso: se detecta ANTES de lanzar (y pagar) la pasada.
        raise CliError("--anclar requiere --ficha <ruta de la ficha del producto>")
    out = Path(args.out or os.environ.get(REPORTS_ENV) or DEFAULT_REPORTS_DIR)
    check_out_dir(out)
    runner = _runner(args, intake)
    plan = build_plan(intake)
    print(f"Lanzando pasada {intake.mode.value} ({cost_hint(intake.mode, len(plan.tasks))})…", file=sys.stderr)
    result = run_pass(intake, runner, plan=plan, agent_timeout=args.timeout)
    report = build_report(result, base_dir=out)
    path = save_report(report, out)
    if args.anclar:
        written = anchor_ficha(Path(intake.ficha_path), path, report.global_score, report.date,
                               product=intake.product, repo=intake.repo_path)
        if written:
            print(f"Anclaje «LEER AL RETOMAR» añadido a {intake.ficha_path}")
        else:
            print(f"La ficha {intake.ficha_path} ya tenía el anclaje de este informe: sin cambios")
    for line in result.log:
        print(f"  · {line}", file=sys.stderr)
    print(f"Informe: {path}")
    if not result.results and result.ligera is None:
        print("⚠️  No se evaluó ninguna dimensión: revisa el log de la pasada.", file=sys.stderr)
        return 3
    if report.global_score is not None:
        print(f"Score global: {report.global_score:.1f}/10".replace(".", ","))
    if report.top:
        print("TOP-5 propuesto para autorización (nada se ejecuta sin tu OK):")
        for n, item in enumerate(report.top, 1):
            print(f"  {n}. {item}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    try:
        if args.ligera:
            r = parse_ligera_output(text)
            print(f"OK · ligera · score {r.score:g}/10 · {len(r.findings)} hallazgos")
        else:
            dims = tuple(sorted(args.dims, key=list(Dimension).index))
            if not dims:
                raise SystemExit("indica --dims (o --ligera)")
            for dim, r in parse_grouped_output(text, dims).items():
                print(f"OK · {dim.value} · score {r.score:g}/10 · {len(r.findings)} hallazgos")
                for w in r.warnings:
                    print(f"  ⚠️ {w}")
    except FormatError as exc:
        print("FORMATO INVÁLIDO:", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    return 0


def cmd_cartera(args: argparse.Namespace) -> int:
    from .portfolio import load_latest_reports, render_portfolio, synthesize

    base = Path(args.out or os.environ.get(REPORTS_ENV) or DEFAULT_REPORTS_DIR)
    if not base.is_dir():
        print(f"No existe la carpeta de informes: {base}", file=sys.stderr)
        return 2
    try:
        md = render_portfolio(synthesize(load_latest_reports(base)))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.save:
        path = base / "_cartera.md"
        path.write_text(md, encoding="utf-8")
        print(f"Síntesis guardada: {path}")
    else:
        print(md, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mvpup", description="Orquestador MVP-UP")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="muestra la planificación sin lanzar nada")
    _add_intake_args(p_plan)
    p_plan.add_argument("--show-prompts", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run", help="ejecuta la pasada y guarda el informe")
    _add_intake_args(p_run)
    p_run.add_argument("--runner", choices=["anthropic", "fake"], default="anthropic")
    p_run.add_argument("--fake-responses", help="JSON {task_key: salida} para --runner fake")
    p_run.add_argument("--model", help="modelo de los agentes (por defecto claude-sonnet-5-5)")
    p_run.add_argument("--out", help=f"carpeta de informes (o ${REPORTS_ENV}; por defecto ./{DEFAULT_REPORTS_DIR})")
    p_run.add_argument("--timeout", type=float, default=900.0, help="segundos por intento de agente")
    p_run.add_argument("--anclar", action="store_true",
                       help="añade a --ficha la sección «⚡ MVP-UP … LEER AL RETOMAR» (opt-in)")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="valida la salida de un agente contra su plantilla")
    p_val.add_argument("file")
    p_val.add_argument("--dims", type=_dims, default=frozenset())
    p_val.add_argument("--ligera", action="store_true")
    p_val.set_defaults(func=cmd_validate)

    p_cart = sub.add_parser("cartera", help="síntesis transversal de 2+ proyectos ya auditados")
    p_cart.add_argument("--out", help=f"carpeta de informes (o ${REPORTS_ENV})")
    p_cart.add_argument("--save", action="store_true", help="guarda <out>/_cartera.md")
    p_cart.set_defaults(func=cmd_cartera)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except IntakeError as exc:
        print(f"Intake inválido: {exc}", file=sys.stderr)
        return 2
    except ModelPolicyError as exc:
        print(f"Modelo no permitido: {exc}", file=sys.stderr)
        return 2
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:  # ficheros inexistentes/ilegibles, JSON inválido
        print(f"Error: {type(exc).__name__}: {redact(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
