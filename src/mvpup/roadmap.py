"""Fase 3 · Roadmap de escalado en tres horizontes + TOP-5 para autorización.

REGLA DE HORIZONTE (explícita; no depende de que los agentes den coste o ejecutor):

1. Horizonte base por impacto × esfuerzo (`HORIZON_RULE`):

   | Impacto | Esfuerzo BAJO | Esfuerzo MEDIO | Esfuerzo ALTO |
   |---------|---------------|----------------|---------------|
   | ALTO    | H1 (quick win)| H2             | H3            |
   | MEDIO   | H2            | — (descartar)  | — (descartar) |
   | BAJO    | backlog       | — (descartar)  | — (descartar) |

2. Ajuste por objetivo de valor: una acción de una dimensión que NO es prioritaria
   (peso ×1) para el objetivo baja UN horizonte (H2 → H3; H3 → «no justificada», no
   se programa). Los quick wins nunca bajan: cuestan poco y rinden mucho.
3. Si ninguna de las dimensiones evaluadas es prioritaria no hay con qué priorizar:
   H2 no se difiere (las apuestas de esfuerzo ALTO siguen exigiendo prioridad).

Así H2 («este mes») queda para lo que mueve el objetivo y H3 para el resto, en vez de
recibir casi todo. «Descartar» nunca entra. Un hallazgo estructural con entradas
programadas en 2+ dimensiones se fusiona en UNA acción (en su horizonte más temprano)
que sube todas esas dimensiones.

El coste y el ejecutor no se inventan: sin fuente (`costs`, p.ej. estimaciones dadas
por el operador) quedan sin informar; el informe no los imprime en cada línea, cuenta
una sola vez cuántas acciones carecen de ellos.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

from .consolidation import Entry, Quadrant, Structural
from .dimensions import Dimension, Objective, weight
from .parsing import Level, shorten

TOP_N = 5
NO_COST = "N/D"
NO_OWNER = "por decidir"


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

# Horizonte BASE por (impacto, esfuerzo). Lo que no está aquí no se programa:
# impacto BAJO con esfuerzo BAJO va al backlog y el resto es «descartar».
HORIZON_RULE: dict[tuple[Level, Level], Horizon] = {
    (Level.ALTO, Level.BAJO): Horizon.H1,
    (Level.ALTO, Level.MEDIO): Horizon.H2,
    (Level.ALTO, Level.ALTO): Horizon.H3,
    (Level.MEDIO, Level.BAJO): Horizon.H2,
}

# La misma regla en una línea, para el informe.
HORIZON_RULE_NOTE = (
    "Regla de horizonte: impacto × esfuerzo (alto×bajo → H1 · alto×medio → H2 · alto×alto → H3 · "
    "medio×bajo → H2). Fuera de las dimensiones prioritarias del objetivo de valor, todo salvo "
    "los quick wins baja un horizonte (y lo que cae más allá de H3 no se programa)."
)


@dataclass(frozen=True)
class RoadmapItem:
    entry: Entry
    horizon: Horizon
    cost: str = NO_COST
    owner: str = NO_OWNER
    queued: bool = False
    related: tuple[Entry, ...] = ()  # entradas fusionadas de un hallazgo estructural
    deferred: bool = False  # bajó un horizonte por no ser de una dimensión prioritaria

    @property
    def has_cost(self) -> bool:
        return self.cost != NO_COST

    @property
    def has_owner(self) -> bool:
        return self.owner != NO_OWNER

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
    horizons = list(Horizon)
    candidates = [
        e
        for q in (Quadrant.QUICK_WINS, Quadrant.APUESTAS, Quadrant.SI_SOBRA_TIEMPO)
        for e in matrix.get(q, ())
    ]
    # Sin ninguna dimensión prioritaria entre lo evaluado no hay con qué priorizar H2.
    any_priority = any(weight(e.dimension, objective) > 1 for e in candidates)

    def item(entry: Entry, horizon: Horizon, deferred: bool = False) -> RoadmapItem:
        cost = costs.get((entry.dimension, entry.finding.id), NO_COST)
        return RoadmapItem(entry, horizon, cost=cost, queued=queued, deferred=deferred)

    for entry in candidates:
        finding = entry.finding
        base = HORIZON_RULE.get((finding.impact, finding.effort)) if finding.effort else None
        if base is None:
            # Fuera de la regla solo llega aquí «si sobra tiempo» de impacto BAJO: backlog.
            roadmap.backlog.append(item(entry, Horizon.H2))
            continue
        priority = weight(entry.dimension, objective) > 1
        if priority or base is Horizon.H1:
            roadmap.by_horizon[base].append(item(entry, base))
        elif base is Horizon.H3:
            roadmap.not_justified.append(item(entry, Horizon.H3, deferred=True))
        elif any_priority:
            later = horizons[horizons.index(base) + 1]
            roadmap.by_horizon[later].append(item(entry, later, deferred=True))
        else:
            roadmap.by_horizon[base].append(item(entry, base))
    _merge_structural(roadmap, structural)
    return roadmap


def _merged_cost(items: list[RoadmapItem]) -> str:
    """Costes conocidos por dimensión (nunca se suman ni se inventan); N/D si no hay ninguno."""
    known = [f"{i.entry.dimension.label}: {i.cost}" for i in items if i.has_cost]
    unknown = [f"{i.entry.dimension.label}: {NO_COST}" for i in items if not i.has_cost]
    return "; ".join(known + unknown) if known else NO_COST


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


TOP_CONTEXT_CHARS = 100  # el hallazgo acompaña a la acción como contexto, en corto


def _describe(item: RoadmapItem) -> str:
    """Línea del TOP-5: la ACCIÓN primero; el hallazgo que la motiva, abreviado, como contexto."""
    tail = " · encolar" if item.queued else ""
    prefix = "[estructural] " if item.related else ""
    finding = item.entry.finding
    context = f" (hallazgo: {shorten(finding.text, TOP_CONTEXT_CHARS)})" if finding.action else ""
    return f"{prefix}{finding.label}{context} · {item.dimension_labels} · {item.horizon.value}{tail}"


def top_five(roadmap: Roadmap) -> list[str]:
    """TOP-5 propuesto: acciones estructurales (fusionadas) primero, luego H1→H3.

    Solo entra lo PROGRAMADO: «descartar», backlog y apuestas no justificadas nunca.
    """
    items = roadmap.all_items()
    ordered = [i for i in items if i.related] + [i for i in items if not i.related]
    return [_describe(i) for i in ordered[:TOP_N]]
