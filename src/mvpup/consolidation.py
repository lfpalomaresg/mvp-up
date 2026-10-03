"""Fase 2 · Consolidación: matriz impacto×esfuerzo y hallazgos estructurales."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from .dimensions import Dimension, Objective, weight
from .parsing import DimensionResult, Finding, Level

MAX_STRUCTURAL = 3


class Quadrant(str, Enum):
    QUICK_WINS = "quick_wins"  # impacto ALTO · esfuerzo BAJO
    APUESTAS = "apuestas"  # impacto ALTO · esfuerzo MEDIO/ALTO
    SI_SOBRA_TIEMPO = "si_sobra_tiempo"  # impacto MEDIO/BAJO · esfuerzo BAJO
    DESCARTAR = "descartar"  # impacto MEDIO/BAJO · esfuerzo MEDIO/ALTO


@dataclass(frozen=True)
class Entry:
    dimension: Dimension
    finding: Finding


@dataclass(frozen=True)
class Structural:
    """Hallazgo que se repite en varias dimensiones (bloquea varias a la vez)."""

    entries: tuple[Entry, ...]

    @property
    def dimensions(self) -> tuple[Dimension, ...]:
        order = list(Dimension)
        return tuple(sorted({e.dimension for e in self.entries}, key=order.index))

    @property
    def label(self) -> str:
        return self.entries[0].finding.text  # entries viene ordenado: mayor impacto primero


_IMPACT_RANK = {Level.ALTO: 0, Level.MEDIO: 1, Level.BAJO: 2}
_EFFORT_RANK = {Level.BAJO: 0, Level.MEDIO: 1, Level.ALTO: 2, None: 3}


def quadrant(finding: Finding) -> Quadrant:
    high_impact = finding.impact is Level.ALTO
    low_effort = finding.effort is Level.BAJO
    if high_impact:
        return Quadrant.QUICK_WINS if low_effort else Quadrant.APUESTAS
    return Quadrant.SI_SOBRA_TIEMPO if low_effort else Quadrant.DESCARTAR


def build_matrix(
    results: Mapping[Dimension, DimensionResult], objective: Objective
) -> dict[Quadrant, list[Entry]]:
    """Coloca TODOS los hallazgos en su cuadrante, ordenados por prioridad.

    Orden dentro de cada cuadrante: impacto, peso de la dimensión según el
    objetivo de valor, esfuerzo y orden canónico de dimensión (determinista).
    """
    matrix: dict[Quadrant, list[Entry]] = {q: [] for q in Quadrant}
    order = list(Dimension)
    for dim, result in results.items():
        for finding in result.findings:
            matrix[quadrant(finding)].append(Entry(dim, finding))
    for entries in matrix.values():
        entries.sort(
            key=lambda e: (
                _IMPACT_RANK[e.finding.impact],
                -weight(e.dimension, objective),
                _EFFORT_RANK[e.finding.effort],
                order.index(e.dimension),
            )
        )
    return matrix


_STOPWORDS = frozenset(
    "sin hay con que los las del una uno por para como esta este estan son ser muy mas "
    "pero sus nos les donde cuando todo toda todos todas nada ningun ninguna falta "
    "existe tiene tienen".split()
)


def _tokens(text: str) -> frozenset[str]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return frozenset(w for w in re.findall(r"[a-z0-9]{3,}", plain) if w not in _STOPWORDS)


def _related(a: frozenset[str], b: frozenset[str]) -> bool:
    shared = len(a & b)
    if shared == 0:
        return False
    if len(a) == 1 and len(b) == 1:
        return True  # «Sin analítica» ≈ «No hay analítica»: mismo único término
    return shared >= 2 and shared / min(len(a), len(b)) >= 0.6


def _canonical(entry: Entry) -> tuple:
    """Orden total independiente del orden en que terminaron los agentes."""
    return (
        _IMPACT_RANK[entry.finding.impact],
        list(Dimension).index(entry.dimension),
        entry.finding.id,
        entry.finding.text,
    )


def structural_findings(results: Mapping[Dimension, DimensionResult]) -> list[Structural]:
    """Agrupa hallazgos parecidos de dimensiones DISTINTAS (máximo 3).

    Heurística determinista por solapamiento léxico: es un candidato que el
    orquestador revisa, no un juicio final. Orden: más dimensiones afectadas y
    mayor impacto primero.
    """
    entries = sorted((Entry(d, f) for d, r in results.items() for f in r.findings), key=_canonical)
    tokens = [_tokens(e.finding.text) for e in entries]
    parent = list(range(len(entries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if entries[i].dimension != entries[j].dimension and _related(tokens[i], tokens[j]):
                parent[find(i)] = find(j)

    clusters: dict[int, list[Entry]] = {}
    for i, entry in enumerate(entries):
        clusters.setdefault(find(i), []).append(entry)
    structural = [
        Structural(tuple(sorted(c, key=_canonical)))
        for c in clusters.values()
        if len({e.dimension for e in c}) >= 2
    ]
    structural.sort(
        key=lambda s: (
            -len(s.dimensions),
            min(_IMPACT_RANK[e.finding.impact] for e in s.entries),
            s.label,
        )
    )
    return structural[:MAX_STRUCTURAL]
