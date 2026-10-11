"""Fase 2 · Score global ponderado por el objetivo de valor (tabla fija)."""

from __future__ import annotations

from collections.abc import Mapping

from .dimensions import Dimension, Objective, weight


def global_score(scores: Mapping[Dimension, float | None], objective: Objective) -> float | None:
    """Media ponderada de las dimensiones evaluadas.

    `None` = N/A o "sin evaluar": no cuenta ni en numerador ni en denominador.
    Devuelve None si no hay ninguna dimensión evaluada.
    """
    total = 0.0
    weights = 0
    for dim, score in scores.items():
        if score is None:
            continue
        w = weight(dim, objective)
        total += score * w
        weights += w
    if weights == 0:
        return None
    return round(total / weights, 1)


def fmt_score(score: float | None, decimals: int | None = None) -> str:
    """Score en formato español («6», «6,5»; con `decimals=1` siempre «6,0»); None → «—».

    Único formateador de scores: informe, comparación y cartera lo comparten para que un
    mismo valor no salga «6/10» en un sitio y «6,0/10» en otro.
    """
    if score is None:
        return "—"
    if decimals is None:
        decimals = 0 if float(score).is_integer() else 1
    return f"{score:.{decimals}f}".replace(".", ",")


def status_icon(score: float | None) -> str:
    if score is None:
        return "⚪"
    if score >= 7:
        return "🟢"
    if score >= 5:
        return "🟡"
    return "🔴"
