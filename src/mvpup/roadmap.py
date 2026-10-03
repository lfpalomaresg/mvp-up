"""Fase 3 · Roadmap de escalado en tres horizontes + TOP-5 para autorización.

Mapeo desde la matriz:
- H1 (esta semana): quick wins.
- H2 (este mes): apuestas de esfuerzo MEDIO + "si sobra tiempo" de impacto MEDIO.
- Backlog: "si sobra tiempo" de impacto BAJO (no se programa).
- H3 (trimestre): apuestas de esfuerzo ALTO, SOLO si su dimensión es prioritaria
  (peso ×2) para el objetivo de valor; si no, quedan como "no justificadas".
- "Descartar" nunca entra.

El coste y el ejecutor no se inventan: quedan como N/D / "por decidir" salvo que
se aporten con fuente (`costs`, p.ej. estimaciones dadas por el operador).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from .consolidation import Entry, Quadrant, Structural
from .dimensions import Dimension, Objective, weight
from .parsing import Level

TOP_N = 5


class Horizon(str, Enum):
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"

    @property
    def title(self) -> str:
        return {"H1": "Esta semana (quick wins)", "H2": "Este mes", "H3": "Trimestre"}[self.value]


@dataclass(frozen=True)
class RoadmapItem:
    entry: Entry
    horizon: Horizon
    cost: str = "N/D"
    owner: str = "por decidir"
    queued: bool = False


@dataclass
class Roadmap:
    by_horizon: dict[Horizon, list[RoadmapItem]] = field(
        default_factory=lambda: {h: [] for h in Horizon}
    )
    not_justified: list[RoadmapItem] = field(default_factory=list)
    backlog: list[RoadmapItem] = field(default_factory=list)
    wip_note: str = ""

    def items(self, horizon: Horizon) -> list[RoadmapItem]:
        return self.by_horizon[horizon]

    def all_items(self) -> list[RoadmapItem]:
        return [i for h in Horizon for i in self.by_horizon[h]]


WIP_NOTE = (
    "El producto no está en los carriles activos (regla WIP): las acciones se marcan "
    "como «encolar»; no se ejecutan sin autorización explícita."
)


def build_roadmap(
    matrix: Mapping[Quadrant, Sequence[Entry]],
    objective: Objective,
    in_wip_lanes: bool = True,
    costs: Mapping[tuple[Dimension, str], str] | None = None,
) -> Roadmap:
    """`costs`: coste con fuente por (dimensión, id de hallazgo); el resto queda N/D."""
    queued = not in_wip_lanes
    costs = costs or {}
    roadmap = Roadmap(wip_note="" if in_wip_lanes else WIP_NOTE)

    def item(entry: Entry, horizon: Horizon) -> RoadmapItem:
        cost = costs.get((entry.dimension, entry.finding.id), "N/D")
        return RoadmapItem(entry, horizon, cost=cost, queued=queued)

    def add(entry: Entry, horizon: Horizon) -> None:
        roadmap.by_horizon[horizon].append(item(entry, horizon))

    for entry in matrix.get(Quadrant.QUICK_WINS, ()):
        add(entry, Horizon.H1)
    for entry in matrix.get(Quadrant.APUESTAS, ()):
        if entry.finding.effort is not Level.ALTO:
            add(entry, Horizon.H2)
        elif weight(entry.dimension, objective) > 1:
            add(entry, Horizon.H3)
        else:
            roadmap.not_justified.append(item(entry, Horizon.H3))
    for entry in matrix.get(Quadrant.SI_SOBRA_TIEMPO, ()):
        if entry.finding.impact is Level.MEDIO:
            add(entry, Horizon.H2)
        else:
            roadmap.backlog.append(item(entry, Horizon.H2))
    return roadmap


def _describe(item: RoadmapItem) -> str:
    tail = " · encolar" if item.queued else ""
    return f"{item.entry.finding.text} · {item.entry.dimension.label} · {item.horizon.value}{tail}"


def top_five(roadmap: Roadmap, structural: Sequence[Structural] = ()) -> list[str]:
    """TOP-5 propuesto: estructurales primero (desbloquean varias dimensiones), luego H1→H3.

    Solo entra lo PROGRAMADO: un estructural se propone como tal únicamente si
    tiene entradas programadas en 2+ dimensiones; lo «descartar», el backlog y
    las apuestas no justificadas nunca entran.
    """
    scheduled = {i.entry: i for i in roadmap.all_items()}
    top: list[str] = []
    covered: set[Entry] = set()
    order = list(Dimension)
    for s in structural:
        # Solo cuenta lo programado: dimensiones y cobertura salen de las entradas en el roadmap.
        items = [scheduled[e] for e in s.entries if e in scheduled]
        dims = sorted({i.entry.dimension for i in items}, key=order.index)
        if len(dims) < 2:
            continue  # ya no es transversal: sus entradas programadas salen como acción normal
        tail = " · encolar" if any(i.queued for i in items) else ""
        labels = " + ".join(d.label for d in dims)
        top.append(f"[estructural] {items[0].entry.finding.text} · {labels}{tail}")
        covered.update(i.entry for i in items)
    for item in roadmap.all_items():
        if item.entry not in covered:
            top.append(_describe(item))
    return top[:TOP_N]
