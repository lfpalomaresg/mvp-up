"""Fase 1 · Ejecución: lanza los agentes por lotes, valida y reintenta.

Reglas de la skill:
- máximo MAX_PARALLEL_AGENTS agentes en paralelo por lote;
- formato inválido (o fallo del agente) → un reintento con prompt reforzado;
- si vuelve a fallar → dimensión "sin evaluar" y se sigue: el informe nunca se
  bloquea por una dimensión.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TypeVar

from .dimensions import MAX_PARALLEL_AGENTS, Dimension, Mode
from .intake import Intake
from .parsing import (
    DimensionResult,
    FormatError,
    LigeraResult,
    parse_grouped_partial,
    parse_ligera_output,
)
from .prompts import build_task_prompt
from .redaction import redact
from .runners import AgentRunner
from .selection import AgentTask, Plan, build_plan

T = TypeVar("T")

MAX_ATTEMPTS = 2  # intento + un reintento
DEFAULT_AGENT_TIMEOUT = 900.0  # segundos por intento
LIGERA_TASK_KEY = "ligera"  # task_key del agente único del modo ligera


@dataclass
class PassResult:
    intake: Intake
    plan: Plan
    results: dict[Dimension, DimensionResult] = field(default_factory=dict)
    unevaluated: tuple[Dimension, ...] = ()
    ligera: LigeraResult | None = None
    log: list[str] = field(default_factory=list)

    @property
    def not_applicable(self) -> tuple[Dimension, ...]:
        return self.plan.not_applicable

    def scores(self) -> dict[Dimension, float | None]:
        """Score por dimensión seleccionada; None = sin evaluar."""
        return {
            d: (self.results[d].score if d in self.results else None)
            for d in self.plan.selected
        }


def reinforce(prompt: str, problems: list[str]) -> str:
    detail = "; ".join(problems) or "error del agente"
    return (
        f"{prompt}\n\n"
        f"ATENCIÓN: tu respuesta anterior no cumplía el formato ({detail}). "
        "Repite el análisis y devuelve EXACTAMENTE los headers ## de la plantilla, "
        "literales, sin texto adicional en ellos."
    )


def _call_with_timeout(fn: Callable[[], T], timeout: float | None, slots: threading.Semaphore) -> T:
    """Ejecuta `fn` en un hilo daemon y abandona la espera al vencer `timeout`.

    `slots` limita las llamadas VIVAS a MAX_PARALLEL_AGENTS: el hueco se libera
    cuando el hilo termina de verdad, no cuando vence el timeout. Un hilo no se
    puede matar, así que un agente colgado retiene su hueco; esperar hueco
    también está acotado por `timeout`, de modo que la pasada nunca se bloquea.
    """
    if not slots.acquire(timeout=timeout):
        raise TimeoutError(f"sin hueco libre para el agente en {timeout:g}s (agentes colgados)")
    box: dict[str, object] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — se re-lanza en el hilo principal
            box["error"] = exc
        finally:
            slots.release()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"el agente no respondió en {timeout:g}s")
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box["value"]  # type: ignore[return-value]


@dataclass(frozen=True)
class _Ctx:
    runner: AgentRunner
    timeout: float | None
    slots: threading.Semaphore


def _call(ctx: _Ctx, prompt: str, key: str, log: list[str], attempt: int) -> str | None:
    try:
        text = _call_with_timeout(
            lambda: ctx.runner.run(prompt, task_key=key), ctx.timeout, ctx.slots
        )
    except Exception as exc:  # noqa: BLE001 — un agente caído no tumba la pasada
        # El texto de una excepción puede llevar URLs con credenciales o cabeceras: se redacta.
        log.append(redact(f"{key}: el agente falló en intento {attempt}: {type(exc).__name__}: {exc}"))
        return None
    if not isinstance(text, str):
        # Un runner mal configurado (p.ej. --fake-responses con un número) no debe tumbar la pasada.
        log.append(f"{key}: el agente no devolvió texto en intento {attempt} ({type(text).__name__})")
        return None
    return text


def _attempt(ctx: _Ctx, prompt: str, key: str, parse: Callable[[str], LigeraResult], log: list[str]) -> LigeraResult | None:
    current = prompt
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = _call(ctx, current, key, log, attempt)
        problems = ["el agente no devolvió respuesta"]
        if text is not None:
            try:
                parsed = parse(text)
            except FormatError as exc:
                problems = exc.problems
                log.append(f"{key}: formato inválido en intento {attempt}: {exc}")
            else:
                log.extend(f"{key}: aviso: {w}" for w in parsed.warnings)
                return parsed
        if attempt < MAX_ATTEMPTS:
            log.append(f"{key}: reintento con prompt reforzado")
            current = reinforce(prompt, problems)
    log.append(f"{key}: sin evaluar tras {MAX_ATTEMPTS} intentos")
    return None


def _run_task(task: AgentTask, intake: Intake, ctx: _Ctx) -> tuple[AgentTask, dict[Dimension, DimensionResult], list[str]]:
    """Ejecuta un agente (1-2 dimensiones) conservando los bloques válidos de cada intento."""
    log: list[str] = []
    prompt = build_task_prompt(task, intake)
    results: dict[Dimension, DimensionResult] = {}
    current = prompt
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = _call(ctx, current, task.key, log, attempt)
        pending = tuple(d for d in task.dimensions if d not in results)
        problems: list[str] = ["el agente no devolvió respuesta"]
        if text is not None:
            parsed, by_dim, structural = parse_grouped_partial(text, task.dimensions)
            # Bloques sobrantes: ruido, no se reintenta por ellos (coste sin información).
            log.extend(f"{task.key}: aviso de formato: {p}" for p in structural)
            for dim in pending:  # lo ya válido de un intento anterior no se pisa
                if dim in parsed:
                    results[dim] = parsed[dim]
                    # Lo descartado por falta de evidencia se ve: nunca un informe «limpio» en silencio.
                    log.extend(f"{task.key}: aviso en {dim.value}: {w}" for w in parsed[dim].warnings)
            problems = [p for d in pending if d in by_dim for p in by_dim[d]]
            if problems:
                log.append(f"{task.key}: formato inválido en intento {attempt}: {'; '.join(problems)}")
        if all(d in results for d in task.dimensions):
            return task, results, log
        if attempt < MAX_ATTEMPTS:
            log.append(f"{task.key}: reintento con prompt reforzado")
            current = reinforce(prompt, problems)
    missing = [d.value for d in task.dimensions if d not in results]
    log.append(f"{task.key}: sin evaluar tras {MAX_ATTEMPTS} intentos: {', '.join(missing)}")
    return task, results, log


def run_pass(
    intake: Intake,
    runner: AgentRunner,
    plan: Plan | None = None,
    agent_timeout: float | None = DEFAULT_AGENT_TIMEOUT,
) -> PassResult:
    plan = plan or build_plan(intake)
    result = PassResult(intake=intake, plan=plan)
    result.log.extend(f"aviso: {w}" for w in plan.warnings)
    ctx = _Ctx(runner, agent_timeout, threading.BoundedSemaphore(MAX_PARALLEL_AGENTS))

    if intake.mode is Mode.LIGERA:
        if plan.tasks:
            prompt = build_task_prompt(plan.tasks[0], intake)
            result.ligera = _attempt(ctx, prompt, LIGERA_TASK_KEY, parse_ligera_output, result.log)
        return result

    unevaluated: list[Dimension] = []
    for batch in plan.batches:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_AGENTS, len(batch))) as pool:
            outcomes = list(pool.map(lambda t: _run_task(t, intake, ctx), batch))
        for task, parsed, log in outcomes:  # orden determinista: el del plan
            result.log.extend(log)
            result.results.update(parsed)
            unevaluated.extend(d for d in task.dimensions if d not in parsed)
    order = list(Dimension)
    result.unevaluated = tuple(sorted(unevaluated, key=order.index))
    return result
