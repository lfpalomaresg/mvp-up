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


def status_icon(score: float | None) -> str:
    if score is None:
        return "⚪"
    if score >= 7:
        return "🟢"
    if score >= 5:
        return "🟡"
    return "🔴"
