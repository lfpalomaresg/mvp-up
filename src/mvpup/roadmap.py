"""Fase 3 · Roadmap de escalado en tres horizontes + TOP-5 para autorización.

Mapeo desde la matriz:
- H1 (esta semana): quick wins.
- H2 (este mes): apuestas de esfuerzo MEDIO + "si sobra tiempo" de impacto MEDIO.
- Backlog: "si sobra tiempo" de impacto BAJO (no se programa).
- H3 (trimestre): apuestas de esfuerzo ALTO, SOLO si su dimensión es prioritaria
  (peso ×2) para el objetivo de valor; si no, quedan como "no justificadas".
- "Descartar" nunca entra.
- Un hallazgo estructural con entradas programadas en 2+ dimensiones se fusiona en
  UNA acción (en su horizonte más temprano) que sube todas esas dimensiones.

El coste y el ejecutor no se inventan: quedan como N/D / "por decidir" salvo que
se aporten con fuente (`costs`, p.ej. estimaciones dadas por el operador).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
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
    def label(self) -> str:
        return HORIZON_LABELS[self]


HORIZON_LABELS: dict[Horizon, str] = {
    Horizon.H1: "Esta semana (quick wins)",
    Horizon.H2: "Este mes",
    Horizon.H3: "Trimestre",
}


@dataclass(frozen=True)
class RoadmapItem:
    entry: Entry
    horizon: Horizon
    cost: str = "N/D"
    owner: str = "por decidir"
    queued: bool = False
    related: tuple[Entry, ...] = ()  # entradas fusionadas de un hallazgo estructural

    @property
    def dimensions(self) -> tuple[Dimension, ...]:
        order = list(Dimension)
        dims = {self.entry.dimension, *(e.dimension for e in self.related)}
        return tuple(sorted(dims, key=order.index))

    @property
    def dimension_labels(self) -> str:
        return " + ".join(d.label for d in self.dimensions)


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
    structural: Sequence[Structural] = (),
) -> Roadmap:
    """`costs`: coste con fuente por (dimensión, id de hallazgo); el resto queda N/D.

    `structural`: hallazgos transversales cuyas entradas programadas se fusionan.
    """
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
    _merge_structural(roadmap, structural)
    return roadmap


def _merged_cost(items: list[RoadmapItem]) -> str:
    """Costes conocidos por dimensión (nunca se suman ni se inventan); N/D si no hay ninguno."""
    known = [f"{i.entry.dimension.label}: {i.cost}" for i in items if i.cost != "N/D"]
    unknown = [f"{i.entry.dimension.label}: N/D" for i in items if i.cost == "N/D"]
    return "; ".join(known + unknown) if known else "N/D"


def _merge_structural(roadmap: Roadmap, structural: Sequence[Structural]) -> None:
    """Fusiona las entradas PROGRAMADAS de cada estructural (2+ dimensiones) en una acción."""
    horizons = list(Horizon)
    for s in structural:
        located = [
            (horizons.index(h), pos, it)
            for h in Horizon
            for pos, it in enumerate(roadmap.by_horizon[h])
            if it.entry in s.entries and not it.related
        ]
        if len({it.entry.dimension for _, _, it in located}) < 2:
            continue  # sin transversalidad programada: cada acción queda como está
        located.sort(key=lambda t: (t[0], s.entries.index(t[2].entry)))
        primary = located[0][2]
        rest = tuple(it.entry for _, _, it in located[1:])
        merged = replace(primary, related=rest, cost=_merged_cost([it for _, _, it in located]))
        for h in Horizon:
            roadmap.by_horizon[h] = [
                merged if it is primary else it
                for it in roadmap.by_horizon[h]
                if it is primary or it.entry not in rest
            ]


def _describe(item: RoadmapItem) -> str:
    tail = " · encolar" if item.queued else ""
    prefix = "[estructural] " if item.related else ""
    return f"{prefix}{item.entry.finding.text} · {item.dimension_labels} · {item.horizon.value}{tail}"


def top_five(roadmap: Roadmap) -> list[str]:
    """TOP-5 propuesto: acciones estructurales (fusionadas) primero, luego H1→H3.

    Solo entra lo PROGRAMADO: «descartar», backlog y apuestas no justificadas nunca.
    """
    items = roadmap.all_items()
    ordered = [i for i in items if i.related] + [i for i in items if not i.related]
    return [_describe(i) for i in ordered[:TOP_N]]
