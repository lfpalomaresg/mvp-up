"""Fase 0 · Intake: los datos que hacen falta antes de lanzar ningún agente."""

from __future__ import annotations

from dataclasses import dataclass, field

from .dimensions import Dimension, Mode, Objective, Stage


class IntakeError(ValueError):
    """El intake está incompleto o es incoherente."""


@dataclass(frozen=True)
class Intake:
    product: str
    stage: Stage
    objective: Objective
    mode: Mode = Mode.EXPRESS
    repo_path: str | None = None
    url: str | None = None
    context: str = ""
    ficha_path: str | None = None
    wip_context: str = ""
    has_software: bool = True
    has_customer_data: bool = True
    add: frozenset[Dimension] = field(default_factory=frozenset)
    remove: frozenset[Dimension] = field(default_factory=frozenset)
    full_confirmed: bool = False

    def __post_init__(self) -> None:
        if not self.product.strip():
            raise IntakeError("el producto no puede estar vacío")
        # Coerción tolerante: permite construir el intake desde strings (CLI/JSON).
        for name, enum in (("stage", Stage), ("objective", Objective), ("mode", Mode)):
            value = getattr(self, name)
            if not isinstance(value, enum):
                try:
                    object.__setattr__(self, name, enum(value))
                except ValueError as exc:
                    valid = ", ".join(e.value for e in enum)
                    raise IntakeError(f"{name} inválido: {value!r} (válidos: {valid})") from exc
        for name in ("add", "remove"):
            try:
                dims = frozenset(Dimension(d) for d in getattr(self, name))
            except ValueError as exc:
                valid = ", ".join(d.value for d in Dimension)
                raise IntakeError(f"dimensión inválida en {name} (válidas: {valid})") from exc
            object.__setattr__(self, name, dims)
        if self.add & self.remove:
            both = ", ".join(sorted(d.value for d in self.add & self.remove))
            raise IntakeError(f"dimensiones a la vez añadidas y quitadas: {both}")
        if self.mode is Mode.FULL and not self.full_confirmed:
            raise IntakeError(
                "modo full = 10 agentes, la pasada cara: requiere confirmación explícita"
            )
