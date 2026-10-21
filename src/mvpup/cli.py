"""CLI: `mvpup plan | run | validate | cartera | compare | html`.

- plan: muestra la selección, los agentes, avisos y el coste orientativo (sin red).
- run: ejecuta la pasada y guarda el informe versionado (MD + JSON).
- validate: valida contra la plantilla la salida de un agente lanzado a mano
  (p.ej. desde subagentes de Claude Code).
- cartera: síntesis transversal de los últimos informes de 2+ productos.
- compare: deltas por dimensión y acciones cerradas/nuevas entre dos informes guardados.
- html: informe HTML autocontenido (sin CDN ni JS externo) a partir de un Markdown.

El disparo es siempre manual; el modo full exige `--confirm-full`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from .config import ModelPolicyError, check_model
from .dimensions import Dimension, Mode, Objective, Stage
from .intake import Intake, IntakeError
from .orchestrator import DEFAULT_AGENT_TIMEOUT
from .parsing import FormatError, parse_grouped_output, parse_ligera_output
from .prompts import build_task_prompt
from .redaction import redact
from .report import Report
from .runners import AgentRunner
from .selection import Plan, build_plan

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

# Tope del fichero de `--context-file`: se adjunta a TODOS los agentes (coste × nº de agentes).
OPERATOR_CONTEXT_MAX_CHARS = 20_000

CRITICAL_OBJECTIVES = (Objective.VENDIBLE, Objective.INVERSION)
CRITICAL_MODEL = "claude-opus-5-5"


class CliError(Exception):
    """Error de uso previsible: mensaje claro y código 2, sin traceback."""


def cost_hint(mode: Mode, agents: int) -> str:
    """Coste orientativo; si el plan se sale de lo calibrado, se escala por agente."""
    if agents <= 0:
        return "sin agentes que lanzar (ninguna dimensión evaluable) · 0 tokens"
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


def _positive_seconds(value: str) -> float:
    """`--timeout`: segundos > 0 (0, negativo o NaN dejarían fallar a todos los agentes tras lanzar)."""
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--timeout debe ser un número de segundos: {value!r}") from exc
    if not seconds > 0:  # `not >` también descarta NaN
        raise argparse.ArgumentTypeError(f"--timeout debe ser mayor que 0: {value!r}")
    return seconds


def _add_intake_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--product", required=True, help="nombre del producto")
    p.add_argument("--stage", required=True, choices=[s.value for s in Stage])
    p.add_argument("--objective", required=True, choices=[o.value for o in Objective])
    p.add_argument("--mode", default=Mode.EXPRESS.value, choices=[m.value for m in Mode])
    p.add_argument("--confirm-full", action="store_true", help="confirma el modo full (10 agentes)")
    p.add_argument("--repo", help="ruta local del repo/carpeta del producto")
    p.add_argument("--url", help="URL desplegada")
    p.add_argument("--context", default="", help="resumen de negocio (texto)")
    p.add_argument("--context-file", metavar="FICHERO.md",
                   help="fichero de texto libre del operador (resultados de tests, URL de producción, "
                        "métricas…) que se adjunta a todos los agentes como «contexto aportado por el "
                        "operador, no verificado», tras redactar secretos")
    p.add_argument("--ficha", help="ruta de la ficha del producto (modo ligera)")
    p.add_argument("--wip-context", default="", help="foco estratégico / carriles WIP")
    p.add_argument("--not-in-wip", action="store_true", help="producto fuera de carriles activos")
    p.add_argument("--add", type=_dims, default=frozenset(), help="dimensiones extra, separadas por comas")
    p.add_argument("--remove", type=_dims, default=frozenset(), help="dimensiones a quitar")
    p.add_argument("--no-software", action="store_true", help="servicio sin software")
    p.add_argument("--no-customer-data", action="store_true", help="sin datos de clientes")


def read_operator_context(path: Path) -> str:
    """Texto de `--context-file`, ya redactado. Cualquier problema es un error de uso (antes de pagar).

    El operador elige el fichero a propósito: no se veta por nombre ni por ruta, la defensa es `redact()`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CliError(f"--context-file: no se pudo leer {path} ({type(exc).__name__})") from exc
    if not text.strip():
        raise CliError(f"--context-file: {path} está vacío")
    # El tope mide el fichero tal cual, antes de recortar blancos: el relleno no lo esquiva.
    if len(text) > OPERATOR_CONTEXT_MAX_CHARS:
        raise CliError(
            f"--context-file: {path} es demasiado largo ({len(text)} caracteres; máx "
            f"{OPERATOR_CONTEXT_MAX_CHARS}): se adjunta a todos los agentes, resume lo esencial"
        )
    return redact(text.strip())


def _intake(args: argparse.Namespace) -> Intake:
    operator_context = read_operator_context(Path(args.context_file)) if args.context_file else ""
    return Intake(
        product=args.product,
        stage=args.stage,
        objective=args.objective,
        mode=args.mode,
        repo_path=args.repo,
        url=args.url,
        context=args.context,
        operator_context=operator_context,
        ficha_path=args.ficha,
        wip_context=args.wip_context,
        in_wip_lanes=not args.not_in_wip,
        has_software=not args.no_software,
        has_customer_data=not args.no_customer_data,
        add=args.add,
        remove=args.remove,
        full_confirmed=args.confirm_full,
    )


def _print_plan(intake: Intake, plan: Plan, file: TextIO) -> None:
    print(f"Producto: {intake.product} · etapa {intake.stage.value} · objetivo {intake.objective.value}", file=file)
    print(f"Modo: {intake.mode.value} · coste orientativo {cost_hint(intake.mode, len(plan.tasks))}", file=file)
    for key, model in critical_models(intake).items():
        print(f"Decisión crítica: el agente {key} usará {model}", file=file)
    print("Dimensiones: " + ", ".join(d.label for d in plan.selected), file=file)
    if plan.not_applicable:
        print("N/A: " + ", ".join(d.label for d in plan.not_applicable), file=file)
    for n, batch in enumerate(plan.batches, 1):
        print(f"Lote {n}: " + " · ".join(t.key for t in batch), file=file)
    for w in plan.warnings:
        print(f"⚠️  {w}", file=file)


def cmd_plan(args: argparse.Namespace) -> int:
    intake = _intake(args)
    plan = build_plan(intake)
    _print_plan(intake, plan, sys.stdout)
    if args.show_prompts:
        for task in plan.tasks:
            print(f"\n===== PROMPT {task.key} =====\n{build_task_prompt(task, intake)}")
    return 0


def check_repo_path(repo: Path) -> None:
    """`--repo` debe ser un directorio real: si no, los agentes auditarían un aviso, no el repo."""
    if repo.is_symlink():
        raise CliError(f"--repo {repo} es un symlink: no se siguen enlaces, pasa la ruta real")
    if not repo.is_dir():
        raise CliError(f"--repo {repo} no existe o no es un directorio: no se lanza ningún agente")


def _runner(args: argparse.Namespace, intake: Intake, plan: Plan) -> AgentRunner:
    if args.runner == "fake":
        from .runners import FakeRunner

        if not args.fake_responses:
            raise CliError("--runner fake requiere --fake-responses <json {task_key: salida}>")
        data = json.loads(Path(args.fake_responses).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--fake-responses debe ser un objeto JSON {task_key: salida}")
        try:
            return FakeRunner(data)
        except TypeError as exc:
            raise CliError(f"--fake-responses: {exc}") from exc
    from .anthropic_runner import (
        AnthropicRunner,
        SnapshotProfile,
        repo_snapshot,
        snapshots_for_tasks,
    )
    from .config import API_KEY_ENV, load_dotenv
    from .orchestrator import LIGERA_TASK_KEY

    load_dotenv(Path.cwd() / ".env")
    if not os.environ.get(API_KEY_ENV):
        raise CliError(f"falta {API_KEY_ENV}: defínela en .env (gitignoreado) o en el entorno")
    # Una instantánea por perfil de agente: el técnico recibe código; el comercial, documentación.
    snapshots: dict[str, str] = {}
    if intake.repo_path and intake.mode is Mode.LIGERA:
        # El agente único de ligera mira todas las dimensiones y se llama con su propia clave.
        snapshots = {LIGERA_TASK_KEY: repo_snapshot(intake.repo_path, profile=SnapshotProfile.BALANCED)}
    elif intake.repo_path:
        snapshots = snapshots_for_tasks(intake.repo_path, plan.tasks)
    return AnthropicRunner(
        model=args.model, snapshot_by_key=snapshots, model_by_key=critical_models(intake)
    )


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
    from .report import build_report, save_report, usage_line

    intake = _intake(args)
    if args.model:
        check_model(args.model)  # la política de modelos va antes que cualquier otra cosa
    # Errores de uso: se detectan ANTES de lanzar (y pagar) la pasada.
    if args.anclar and not intake.ficha_path:
        raise CliError("--anclar requiere --ficha <ruta de la ficha del producto>")
    if args.dry_run and (args.runner == "fake" or args.fake_responses):
        raise CliError("--dry-run ya simula los agentes: no se combina con --runner fake/--fake-responses")
    if args.fake_responses and args.runner != "fake":
        # Sin esto el fichero se ignoraba y la pasada salía con agentes REALES (y coste).
        raise CliError("--fake-responses solo tiene sentido con --runner fake (¿querías simular la pasada?)")
    if args.dry_run and args.anclar:
        raise CliError("--anclar no se combina con --dry-run: un informe sintético no se ancla en una ficha real")
    if intake.repo_path:
        # En TODOS los caminos (real, fake, dry-run) y antes de leer .env o pedir la API key.
        check_repo_path(Path(intake.repo_path))
    out = Path(args.out or os.environ.get(REPORTS_ENV) or DEFAULT_REPORTS_DIR)
    check_out_dir(out)
    plan = build_plan(intake)
    if args.dry_run:
        from .dryrun import dry_run_responses
        from .runners import FakeRunner

        print("DRY-RUN: pasada simulada con datos sintéticos (sin red, sin API key, sin coste).", file=sys.stderr)
        runner: AgentRunner = FakeRunner(dry_run_responses(plan, intake.mode))
    else:
        runner = _runner(args, intake, plan)
    _print_plan(intake, plan, sys.stderr)
    print(f"Lanzando pasada {intake.mode.value} ({cost_hint(intake.mode, len(plan.tasks))})…", file=sys.stderr)
    result = run_pass(intake, runner, plan=plan, agent_timeout=args.timeout)
    report = build_report(result, base_dir=out, dry_run=args.dry_run)
    path = save_report(report, out)
    for line in result.log:
        print(f"  · {line}", file=sys.stderr)
    print(f"Informe: {path}")
    consumption = usage_line(result)
    if consumption:
        print(consumption.replace("**", ""))
    if args.html:
        print(f"HTML: {write_html(path)}")
    if not result.results and result.ligera is None:
        print("⚠️  No se evaluó ninguna dimensión: revisa el log de la pasada.", file=sys.stderr)
        if intake.ficha_path:
            print(f"La ficha {intake.ficha_path} no se ancla a una pasada vacía.", file=sys.stderr)
        return 3
    if intake.ficha_path and args.dry_run:
        print(f"DRY-RUN: la ficha {intake.ficha_path} no se toca (datos sintéticos).", file=sys.stderr)
    elif intake.ficha_path:
        _anchor(Path(intake.ficha_path), intake, report, path, block=args.anclar)
    if report.global_score is not None:
        print(f"Score global: {report.global_score:.1f}/10".replace(".", ","))
    if report.top:
        print("TOP-5 propuesto para autorización (nada se ejecuta sin tu OK):")
        for n, item in enumerate(report.top, 1):
            print(f"  {n}. {item}")
    return 0


def _anchor(ficha: Path, intake: Intake, report: Report, path: Path, block: bool) -> None:
    """Ancla el informe en la ficha: frontmatter siempre; bloque «LEER AL RETOMAR» solo con --anclar."""
    from .ficha import anchor_ficha, anchor_frontmatter

    if anchor_frontmatter(ficha, report.date, report.global_score, path, product=intake.product):
        print(f"Ficha {ficha}: frontmatter actualizado (mvpup_date, mvpup_score, mvpup_report)")
    else:
        print(f"Ficha {ficha}: frontmatter ya anclado a este informe, sin cambios")
    if not block:
        return
    if anchor_ficha(ficha, path, report.global_score, report.date, product=intake.product, repo=intake.repo_path):
        print(f"Anclaje «LEER AL RETOMAR» añadido a {ficha}")
    else:
        print(f"La ficha {ficha} ya tenía el anclaje de este informe: sin cambios")


def cmd_validate(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    try:
        if args.ligera:
            ligera = parse_ligera_output(text)
            print(f"OK · ligera · score {ligera.score:g}/10 · {len(ligera.findings)} hallazgos")
            for w in ligera.warnings:
                print(f"  ⚠️ {w}")
        else:
            dims = tuple(sorted(args.dims, key=list(Dimension).index))
            if not dims:
                raise CliError("indica --dims <dimensiones> (o --ligera)")
            for dim, result in parse_grouped_output(text, dims).items():
                print(f"OK · {dim.value} · score {result.score:g}/10 · {len(result.findings)} hallazgos")
                for w in result.warnings:
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


def load_report_json(path: Path) -> dict[str, Any]:
    """JSON gemelo de un informe guardado (acepta la ruta del `.md` o del `.json`)."""
    json_path = path.with_suffix(".json") if path.suffix.lower() == ".md" else path
    if path.suffix.lower() == ".md" and not json_path.exists():
        raise CliError(f"el informe {path} no tiene JSON gemelo ({json_path.name}): no se puede comparar")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("scores"), dict):
        raise CliError(f"{json_path} no parece el JSON de un informe MVP-UP (falta `scores`)")
    return data


def cmd_compare(args: argparse.Namespace) -> int:
    from .compare import diff_reports, render_diff

    previous = load_report_json(Path(args.previous))
    current = load_report_json(Path(args.current))
    md = render_diff(diff_reports(previous, current))
    if args.save:
        target = Path(args.save)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8")
        print(f"Comparación guardada: {target}")
    else:
        print(md, end="")
    return 0


def write_html(markdown_path: Path, target: Path | None = None) -> Path:
    """Escribe el HTML autocontenido de un Markdown (por defecto, junto a él con extensión .html)."""
    from .htmlreport import render_html

    html_path = target or markdown_path.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(markdown_path.read_text(encoding="utf-8")), encoding="utf-8")
    return html_path


def cmd_html(args: argparse.Namespace) -> int:
    path = write_html(Path(args.file), Path(args.out) if args.out else None)
    print(f"HTML: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(prog="mvpup", description="Orquestador MVP-UP")
    parser.add_argument("--version", action="version", version=f"mvpup {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="muestra la planificación sin lanzar nada")
    _add_intake_args(p_plan)
    p_plan.add_argument("--show-prompts", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run", help="ejecuta la pasada y guarda el informe")
    _add_intake_args(p_run)
    p_run.add_argument("--runner", choices=["anthropic", "fake"], default="anthropic")
    p_run.add_argument("--fake-responses", help="JSON {task_key: salida} para --runner fake")
    p_run.add_argument("--dry-run", action="store_true",
                       help="pasada completa con agentes simulados y datos sintéticos (sin red ni API key)")
    p_run.add_argument("--model", help="modelo de los agentes (por defecto claude-sonnet-5-5)")
    p_run.add_argument("--out", help=f"carpeta de informes (o ${REPORTS_ENV}; por defecto ./{DEFAULT_REPORTS_DIR})")
    p_run.add_argument("--timeout", type=_positive_seconds, default=DEFAULT_AGENT_TIMEOUT,
                       help="segundos por intento de agente (> 0)")
    p_run.add_argument("--anclar", action="store_true",
                       help="añade a --ficha la sección «⚡ MVP-UP … LEER AL RETOMAR» (opt-in)")
    p_run.add_argument("--html", action="store_true", help="guarda también el informe como HTML autocontenido")
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

    p_cmp = sub.add_parser("compare", help="deltas entre dos informes ya guardados (anterior → nuevo)")
    p_cmp.add_argument("previous", help="informe anterior (.md con JSON gemelo, o el .json)")
    p_cmp.add_argument("current", help="informe nuevo (.md con JSON gemelo, o el .json)")
    p_cmp.add_argument("--save", help="guarda el resumen Markdown en esta ruta en vez de imprimirlo")
    p_cmp.set_defaults(func=cmd_compare)

    p_html = sub.add_parser("html", help="informe HTML autocontenido (sin CDN ni JS) a partir de un .md")
    p_html.add_argument("file", help="Markdown de un informe, comparación o síntesis de cartera")
    p_html.add_argument("--out", help="ruta del .html (por defecto, junto al .md)")
    p_html.set_defaults(func=cmd_html)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command: Callable[[argparse.Namespace], int] = args.func
    try:
        return command(args)
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
    except KeyboardInterrupt:
        # Convención POSIX: 128 + SIGINT. Sin traceback: el operador ya sabe que ha cortado.
        print("Interrumpido por el usuario: la pasada se ha cancelado y no se ha guardado informe.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
