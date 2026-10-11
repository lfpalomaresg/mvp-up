"""Fase 4 · Comparación con la pasada anterior (Δ por dimensión y evolución).

Lee el JSON gemelo del último informe. Reglas de la skill:
- un score que BAJA se señala en rojo con causa probable;
- si el objetivo de valor cambió, el score anterior se recalcula con los pesos
  nuevos y los Δ se marcan como «no comparables directamente»;
- un informe anterior de hace más de 6 meses → aviso de comparación poco significativa.

Qué acciones «se hicieron» no se puede saber sin el operador: se informa de qué
acciones del roadmap anterior ya no aparecen como hallazgo (candidatas a hechas)
y cuáles siguen abiertas, para que el operador lo confirme.
"""

from __future__ import annotations

import calendar
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date
from typing import TYPE_CHECKING, Any, TypeGuard

from .dimensions import Dimension
from .parsing import Finding
from .scoring import global_score

if TYPE_CHECKING:
    from .report import Report

STALE_MONTHS = 6


def older_than_six_months(previous: date, today: date) -> bool:
    """Más de 6 meses NATURALES (31-ago + 6 meses = 28/29-feb)."""
    month_index = previous.month - 1 + STALE_MONTHS
    year, month = previous.year + month_index // 12, month_index % 12 + 1
    day = min(previous.day, calendar.monthrange(year, month)[1])
    return today > date(year, month, day)


def _fmt(value: float) -> str:
    return (f"{value:g}" if float(value).is_integer() else f"{value:.1f}").replace(".", ",")


def format_delta(previous: float | None, current: float | None) -> str:
    if current is None:
        return "—"
    if previous is None:
        return "nuevo"
    diff = round(current - previous, 1)
    if diff == 0:
        return "="
    if diff > 0:
        return f"+{_fmt(diff)}"
    return f"🔴 -{_fmt(-diff)}"


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in plain if not unicodedata.combining(c)).split())


def _is_number(value: Any) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _prev_scores(previous: dict[str, Any], ignored: list[str]) -> dict[Dimension, float | None]:
    """Scores anteriores legibles; lo que no sea número (o null) se ignora y se anota."""
    raw = previous.get("scores")
    if not isinstance(raw, dict):
        ignored.append("scores")
        return {}
    scores: dict[Dimension, float | None] = {}
    for key, value in raw.items():
        try:
            dim = Dimension(key)
        except ValueError:
            continue
        if value is None or _is_number(value):
            scores[dim] = None if value is None else float(value)
        else:
            ignored.append(f"scores.{key}")
    return scores


def _both_scored(
    current: Mapping[Dimension, float | None], previous: Mapping[Dimension, float | None]
) -> list[tuple[Dimension, float, float]]:
    """(dimensión, anterior, actual) solo donde las dos pasadas tienen score."""
    out: list[tuple[Dimension, float, float]] = []
    for dim, score in current.items():
        prev = previous.get(dim)
        if score is not None and prev is not None:
            out.append((dim, prev, score))
    return out


def _drop_cause(dim: Dimension, findings: Sequence[Finding], prev_findings: Any) -> str:
    """Causa probable = hallazgos de impacto ALTO nuevos en esa dimensión, con evidencia.

    No se inventa causalidad: sin hallazgos de la pasada anterior no se atribuye nada.
    """
    if not isinstance(prev_findings, list):
        return "Sin datos de hallazgos de la pasada anterior para atribuir causa (revisar a mano)."
    before = {
        _norm(f.get("text", ""))
        for f in prev_findings
        if isinstance(f, dict) and f.get("dimension") == dim.value
    }
    new_high = [f for f in findings if f.impact.value == "A" and _norm(f.text) not in before]
    if not new_high:
        return "Causa: sin hallazgo nuevo de impacto alto que lo explique (revisar a mano)."
    cited = "; ".join(f"{f.text} (Evidencia: {f.evidence})" for f in new_high[:2])
    return f"Causa probable (hallazgo nuevo desde la pasada anterior, a verificar): {cited}."


def compare_with_previous(report: Report, previous: dict[str, Any]) -> None:
    """Rellena `report.deltas` y `report.evolution` a partir del JSON anterior."""
    pr = report.pass_result
    intake = report.intake
    ignored: list[str] = []  # campos del JSON anterior con un tipo inesperado (se avisa, no se revienta)
    prev_scores = _prev_scores(previous, ignored)
    current = pr.scores()
    evolution: list[str] = []

    prev_date_raw = previous.get("date", "")
    try:
        prev_date = date.fromisoformat(prev_date_raw)
    except (TypeError, ValueError):
        prev_date = None
        if prev_date_raw:
            ignored.append("date")
    header = f"- Pasada anterior: {prev_date_raw if prev_date else 'fecha desconocida'}"
    prev_global = previous.get("global_score")
    if _is_number(prev_global):
        header += f" · score global {_fmt(prev_global)}/10"
    elif prev_global is not None:
        ignored.append("global_score")
    evolution.append(header)

    if prev_date and older_than_six_months(prev_date, report.date):
        evolution.append(
            "- ⚠️ El informe anterior tiene más de 6 meses: la comparación puede no ser "
            "significativa (el producto pudo cambiar de etapa)."
        )
    if previous.get("stage") and previous["stage"] != intake.stage.value:
        evolution.append(
            f"- ⚠️ Cambio de etapa: {previous['stage']} → {intake.stage.value} "
            "(la selección express de dimensiones puede no coincidir)."
        )

    prev_objective = previous.get("objective")
    objective_changed = bool(prev_objective) and prev_objective != intake.objective.value
    if objective_changed:
        recomputed = global_score(prev_scores, intake.objective)
        evolution.append(
            f"- ⚠️ El objetivo de valor cambió ({prev_objective} → {intake.objective.value}): "
            "los Δ son **no comparables directamente**. Score anterior recalculado con los "
            f"pesos nuevos: {_fmt(recomputed) + '/10' if recomputed is not None else 'N/D'}."
        )

    for dim, score in current.items():
        prev = prev_scores.get(dim)
        if objective_changed and prev is not None and score is not None:
            # Con pesos distintos el Δ no es evolución comparable: se muestra sin juicio.
            report.deltas[dim] = f"n/c ({_fmt(prev)}→{_fmt(score)})"
        else:
            report.deltas[dim] = format_delta(prev, score)

    both = _both_scored(current, prev_scores)
    if objective_changed:
        moved = [f"{d.label} {_fmt(p)} → {_fmt(s)}" for d, p, s in both if s != p]
        if moved:
            evolution.append(
                "- Variaciones por dimensión (sin valorar, objetivo cambiado): " + "; ".join(moved) + "."
            )
    else:
        prev_findings = previous.get("findings")
        for dim, prev, score in both:
            if score < prev:
                evolution.append(
                    f"- 🔴 {dim.label} bajó {_fmt(prev)} → {_fmt(score)}. "
                    f"{_drop_cause(dim, pr.results[dim].findings, prev_findings)}"
                )
        risen = [d.label for d, p, s in both if s > p]
        if risen:
            evolution.append(f"- Subieron: {', '.join(risen)}.")

    raw_roadmap = previous.get("roadmap")
    if raw_roadmap is not None and not isinstance(raw_roadmap, list):
        ignored.append("roadmap")
        raw_roadmap = []
    actions = [a for a in raw_roadmap or [] if isinstance(a, dict) and isinstance(a.get("action"), str) and a["action"]]
    if actions:
        open_texts = {_norm(f.text) for r in pr.results.values() for f in r.findings}
        gone = [a for a in actions if _norm(a["action"]) not in open_texts]
        evolution.append(
            f"- Acciones del roadmap anterior que ya no aparecen como hallazgo: {len(gone)}/{len(actions)} "
            "(candidatas a hechas; confirmar con el operador)."
        )
        evolution.extend(f"  - ✅? {a['action']}" for a in gone)
        evolution.extend(
            f"  - ⏳ sigue abierta: {a['action']}" for a in actions if a not in gone
        )
    if ignored:
        evolution.append(
            "- ⚠️ Campos ilegibles en el JSON del informe anterior (ignorados en la comparación): "
            + ", ".join(ignored) + "."
        )
    report.evolution = evolution

