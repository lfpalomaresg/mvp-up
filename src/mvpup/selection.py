"""Fase 1 (planificación): qué dimensiones se evalúan y cómo se reparten en agentes."""

from __future__ import annotations

from dataclasses import dataclass

from .dimensions import (
    AFFINE_PAIRS,
    EXPRESS_BY_STAGE,
    MAX_PARALLEL_AGENTS,
    SOFTWARE_ONLY,
    Dimension,
    Mode,
)
from .intake import Intake


@dataclass(frozen=True)
class AgentTask:
    """Un agente a lanzar: 1 dimensión, o 2 afines agrupadas en express."""

    dimensions: tuple[Dimension, ...]

    @property
    def key(self) -> str:
        return "+".join(d.value for d in self.dimensions)


@dataclass(frozen=True)
class Plan:
    selected: tuple[Dimension, ...]
    not_applicable: tuple[Dimension, ...]
    tasks: tuple[AgentTask, ...]
    warnings: tuple[str, ...] = ()

    @property
    def batches(self) -> list[list[AgentTask]]:
        """Lotes de como máximo MAX_PARALLEL_AGENTS agentes en paralelo."""
        return [
            list(self.tasks[i : i + MAX_PARALLEL_AGENTS])
            for i in range(0, len(self.tasks), MAX_PARALLEL_AGENTS)
        ]


def not_applicable(intake: Intake) -> frozenset[Dimension]:
    na: set[Dimension] = set()
    if not intake.has_software:
        na |= SOFTWARE_ONLY
        if not intake.has_customer_data:
            na.add(Dimension.SEGURIDAD)
    return frozenset(na)


def select_dimensions(intake: Intake) -> tuple[tuple[Dimension, ...], tuple[Dimension, ...]]:
    """Devuelve (seleccionadas, N/A) en el orden canónico del catálogo."""
    if intake.mode is Mode.EXPRESS:
        base = set(EXPRESS_BY_STAGE[intake.stage])
    else:
        # full y ligera miran todas; ligera las cubre con un único agente.
        base = set(Dimension)
    wanted = (base | intake.add) - intake.remove
    na = not_applicable(intake)
    order = list(Dimension)
    selected = tuple(d for d in order if d in wanted and d not in na)
    skipped = tuple(d for d in order if d in wanted and d in na)
    return selected, skipped


MIN_EXPRESS_AGENTS = 3


def group_tasks(dims: tuple[Dimension, ...], mode: Mode) -> tuple[AgentTask, ...]:
    """Reparte dimensiones en agentes.

    Express agrupa parejas afines para ahorrar coste, pero nunca por debajo de
    MIN_EXPRESS_AGENTS agentes (la skill fija express en 3-5 agentes).
    """
    if mode is Mode.LIGERA:
        return (AgentTask(dims),) if dims else ()
    if mode is Mode.FULL:
        return tuple(AgentTask((d,)) for d in dims)
    remaining = list(dims)
    tasks: list[AgentTask] = []
    while remaining:
        head = remaining.pop(0)
        agents_if_paired = len(tasks) + len(remaining)  # head+pareja cuentan como 1
        partner = None
        if agents_if_paired >= MIN_EXPRESS_AGENTS:
            partner = next(
                (d for d in remaining if frozenset({head, d}) in AFFINE_PAIRS), None
            )
        if partner is not None:
            remaining.remove(partner)
            tasks.append(AgentTask((head, partner)))
        else:
            tasks.append(AgentTask((head,)))
    return tuple(tasks)


MAX_EXPRESS_AGENTS = 5


def build_plan(intake: Intake) -> Plan:
    selected, skipped = select_dimensions(intake)
    tasks = group_tasks(selected, intake.mode)
    warnings: list[str] = []
    if intake.mode is Mode.EXPRESS:
        # Añadir/quitar dimensiones es decisión del operador: se avisa, no se bloquea.
        if len(tasks) < MIN_EXPRESS_AGENTS:
            warnings.append(
                f"express con {len(tasks)} agente(s): por debajo de los 3-5 habituales"
            )
        elif len(tasks) > MAX_EXPRESS_AGENTS:
            warnings.append(
                f"express con {len(tasks)} agentes: por encima de 5; valora el modo full"
            )
    if not tasks:
        warnings.append("no queda ninguna dimensión evaluable")
    return Plan(selected, skipped, tasks, tuple(warnings))
