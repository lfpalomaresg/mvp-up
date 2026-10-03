"""Catálogo FIJO de dimensiones, etapas, objetivos de valor y pesos.

Fuente: skill/SKILL.md y skill/references/dimensiones.md. Estas tablas son
fijas a propósito: inventar pesos por sesión rompe la comparabilidad de los Δ.
"""

from __future__ import annotations

from enum import Enum


class Dimension(str, Enum):
    TECNICA = "tecnica"
    SEGURIDAD = "seguridad"
    LEGAL = "legal"
    PRODUCTO_UX = "producto_ux"
    COMERCIAL = "comercial"
    MARKETING = "marketing"
    MERCADO = "mercado"
    ECONOMICA = "economica"
    OPERATIVA = "operativa"
    DATOS = "datos"

    @property
    def label(self) -> str:
        return LABELS[self]


LABELS: dict[Dimension, str] = {
    Dimension.TECNICA: "Técnica",
    Dimension.SEGURIDAD: "Seguridad",
    Dimension.LEGAL: "Legal",
    Dimension.PRODUCTO_UX: "Producto / UX",
    Dimension.COMERCIAL: "Comercial",
    Dimension.MARKETING: "Marketing y hype",
    Dimension.MERCADO: "Mercado",
    Dimension.ECONOMICA: "Económica",
    Dimension.OPERATIVA: "Operativa",
    Dimension.DATOS: "Datos y medición",
}


class Stage(str, Enum):
    IDEA = "idea"
    MVP = "mvp"
    PRODUCCION = "produccion"
    FACTURANDO = "facturando"


class Objective(str, Enum):
    INGRESOS = "ingresos"
    VENDIBLE = "vendible"
    INVERSION = "inversion"
    DEPENDENCIA = "dependencia"


class Mode(str, Enum):
    EXPRESS = "express"
    FULL = "full"
    LIGERA = "ligera"


D = Dimension

# Selección automática en modo express según la etapa.
EXPRESS_BY_STAGE: dict[Stage, tuple[Dimension, ...]] = {
    Stage.IDEA: (D.MERCADO, D.PRODUCTO_UX, D.COMERCIAL, D.ECONOMICA),
    Stage.MVP: (D.TECNICA, D.PRODUCTO_UX, D.COMERCIAL, D.MARKETING),
    Stage.PRODUCCION: (D.MARKETING, D.COMERCIAL, D.MERCADO, D.ECONOMICA),
    Stage.FACTURANDO: (D.ECONOMICA, D.OPERATIVA, D.SEGURIDAD, D.LEGAL, D.DATOS),
}

# Dimensiones con peso ×2 según el objetivo de valor.
DOUBLE_WEIGHT_BY_OBJECTIVE: dict[Objective, frozenset[Dimension]] = {
    Objective.INGRESOS: frozenset({D.COMERCIAL, D.MARKETING, D.ECONOMICA}),
    Objective.VENDIBLE: frozenset({D.LEGAL, D.TECNICA, D.OPERATIVA}),
    Objective.INVERSION: frozenset({D.MERCADO, D.ECONOMICA, D.DATOS}),
    Objective.DEPENDENCIA: frozenset({D.OPERATIVA, D.DATOS, D.PRODUCTO_UX}),
}

# Dimensiones que no aplican a un producto sin software.
SOFTWARE_ONLY: frozenset[Dimension] = frozenset({D.TECNICA})

# Parejas afines que pueden compartir agente en express (nunca más de 2).
AFFINE_PAIRS: tuple[frozenset[Dimension], ...] = (
    frozenset({D.TECNICA, D.SEGURIDAD}),
    frozenset({D.COMERCIAL, D.MARKETING}),
    frozenset({D.MERCADO, D.ECONOMICA}),
    frozenset({D.LEGAL, D.OPERATIVA}),
)

MAX_PARALLEL_AGENTS = 5
MAX_FINDINGS = 7


def weight(dim: Dimension, objective: Objective) -> int:
    return 2 if dim in DOUBLE_WEIGHT_BY_OBJECTIVE[objective] else 1
