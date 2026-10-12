"""Fase 4 · Comparación con la pasada anterior (Δ por dimensión y evolución).

Dos entradas:
- `compare_with_previous(report, previous)`: rellena la sección «Evolución» del
  informe que se está generando a partir del JSON gemelo de la pasada anterior.
- `diff_reports(previous, current)`: compara dos informes YA guardados (sus JSON)
  y devuelve deltas por dimensión y acciones cerradas/nuevas/abiertas, para
  `mvpup compare <anterior> <nuevo>`.

Reglas de la skill:
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
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, TypeGuard

from .dimensions import Dimension, Objective
from .parsing import Finding
from .scoring import fmt_score, global_score

if TYPE_CHECKING:
    from .report import Report

STALE_MONTHS = 6


def older_than_six_months(previous: date, today: date) -> bool:
    """Más de 6 meses NATURALES (31-ago + 6 meses = 28/29-feb)."""
    month_index = previous.month - 1 + STALE_MONTHS
    year, month = previous.year + month_index // 12, month_index % 12 + 1
    day = min(previous.day, calendar.monthrange(year, month)[1])
    return today > date(year, month, day)


def _global(value: float | None) -> str:
    """Score global con un decimal y «/10», como en la cabecera del informe («6,0/10»)."""
    return "—" if value is None else fmt_score(value, 1) + "/10"


def format_delta(previous: float | None, current: float | None) -> str:
    if current is None:
        return "—"
    if previous is None:
        return "nuevo"
    diff = round(current - previous, 1)
    if diff == 0:
        return "="
    if diff > 0:
        return f"+{fmt_score(diff)}"
    return f"🔴 -{fmt_score(-diff)}"


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in plain if not unicodedata.combining(c)).split())


def _is_number(value: Any) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --- lectura tolerante del JSON de un informe -------------------------------------------------
# Un campo con un tipo inesperado se ignora y se anota en `ignored`: nunca revienta.


def _scores_of(data: Mapping[str, Any], ignored: list[str]) -> dict[Dimension, float | None]:
    """Scores legibles; lo que no sea número (o null) se ignora y se anota."""
    raw = data.get("scores")
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


def _date_of(data: Mapping[str, Any], ignored: list[str]) -> date | None:
    raw = data.get("date")
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    if raw:
        ignored.append("date")
    return None


def _global_of(data: Mapping[str, Any], ignored: list[str]) -> float | None:
    value = data.get("global_score")
    if _is_number(value):
        return float(value)
    if value is not None:
        ignored.append("global_score")
    return None


def _objective_of(data: Mapping[str, Any], ignored: list[str]) -> Objective | None:
    raw = data.get("objective")
    if raw is None:
        return None
    try:
        return Objective(raw)
    except ValueError:
        ignored.append("objective")
        return None


@dataclass(frozen=True)
class _Action:
    """Acción de un roadmap guardado y las claves (normalizadas) por las que se la reconoce.

    Desde que los agentes dan una acción por hallazgo, el roadmap guarda la acción y, aparte,
    el hallazgo que la motiva. En los informes antiguos la «acción» ERA el texto del hallazgo.
    Para casar pasadas de ambos formatos una acción se reconoce por su texto O por su hallazgo.
    """

    text: str
    keys: frozenset[str]


def _actions_of(data: Mapping[str, Any], ignored: list[str]) -> list[_Action]:
    """Acciones del roadmap, sin duplicados y en su orden."""
    raw = data.get("roadmap")
    if raw is not None and not isinstance(raw, list):
        ignored.append("roadmap")
        raw = []
    seen: set[str] = set()
    actions: list[_Action] = []
    for item in raw or []:
        if not isinstance(item, dict) or not isinstance(item.get("action"), str) or not item["action"]:
            continue
        key = _norm(item["action"])
        if key in seen:
            continue
        seen.add(key)
        finding = item.get("finding")
        keys = {key, _norm(finding)} if isinstance(finding, str) and finding else {key}
        actions.append(_Action(item["action"], frozenset(keys)))
    return actions


def _finding_texts(data: Mapping[str, Any], dim: Dimension | None = None) -> set[str]:
    """Hallazgos (normalizados) del informe; `dim` los restringe a una dimensión."""
    raw = data.get("findings")
    if not isinstance(raw, list):
        return set()
    return {
        _norm(f["text"])
        for f in raw
        if isinstance(f, dict) and isinstance(f.get("text"), str)
        and (dim is None or f.get("dimension") == dim.value)
    }


def _present(data: Mapping[str, Any], actions: Sequence[_Action]) -> set[str]:
    """Todo lo que un informe «tiene abierto»: sus acciones, sus hallazgos y las acciones de estos."""
    present = _finding_texts(data)
    for action in actions:
        present |= action.keys
    raw = data.get("findings")
    for f in raw if isinstance(raw, list) else []:
        if isinstance(f, dict) and isinstance(f.get("action"), str) and f["action"]:
            present.add(_norm(f["action"]))
    return present


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


def _context_warnings(
    previous: Mapping[str, Any],
    prev_scores: Mapping[Dimension, float | None],
    prev_date: date | None,
    current_date: date,
    current_stage: str | None,
    current_objective: Objective | None,
) -> tuple[list[str], bool]:
    """Avisos comunes (antigüedad, etapa, objetivo). Devuelve (avisos, objetivo cambiado)."""
    warnings: list[str] = []
    if prev_date and older_than_six_months(prev_date, current_date):
        warnings.append(
            "⚠️ El informe anterior tiene más de 6 meses: la comparación puede no ser "
            "significativa (el producto pudo cambiar de etapa)."
        )
    prev_stage = previous.get("stage")
    if isinstance(prev_stage, str) and current_stage and prev_stage != current_stage:
        warnings.append(
            f"⚠️ Cambio de etapa: {prev_stage} → {current_stage} "
            "(la selección express de dimensiones puede no coincidir)."
        )
    prev_objective = previous.get("objective")
    changed = (
        isinstance(prev_objective, str) and bool(prev_objective)
        and current_objective is not None and prev_objective != current_objective.value
    )
    if changed and current_objective is not None:
        recomputed = global_score(prev_scores, current_objective)
        warnings.append(
            f"⚠️ El objetivo de valor cambió ({prev_objective} → {current_objective.value}): "
            "los Δ son **no comparables directamente**. Score anterior recalculado con los "
            f"pesos nuevos: {fmt_score(recomputed) + '/10' if recomputed is not None else 'N/D'}."
        )
    return warnings, changed


def _delta(prev: float | None, score: float | None, objective_changed: bool) -> str:
    if objective_changed and prev is not None and score is not None:
        # Con pesos distintos el Δ no es evolución comparable: se muestra sin juicio.
        return f"n/c ({fmt_score(prev)}→{fmt_score(score)})"
    return format_delta(prev, score)


def _drop_cause(dim: Dimension, findings: Sequence[Finding], previous: Mapping[str, Any]) -> str:
    """Causa probable = hallazgos de impacto ALTO nuevos en esa dimensión, con evidencia.

    No se inventa causalidad: sin hallazgos de la pasada anterior no se atribuye nada.
    """
    if not isinstance(previous.get("findings"), list):
        return "Sin datos de hallazgos de la pasada anterior para atribuir causa (revisar a mano)."
    before = _finding_texts(previous, dim)
    new_high = [f for f in findings if f.impact.value == "A" and _norm(f.text) not in before]
    if not new_high:
        return "Causa: sin hallazgo nuevo de impacto alto que lo explique (revisar a mano)."
    cited = "; ".join(f"{f.text} (Evidencia: {f.evidence})" for f in new_high[:2])
    return f"Causa probable (hallazgo nuevo desde la pasada anterior, a verificar): {cited}."


def _ignored_line(ignored: Sequence[str], which: str) -> str:
    return (
        f"⚠️ Campos ilegibles en el JSON del informe {which} (ignorados en la comparación): "
        + ", ".join(ignored) + "."
    )


def compare_with_previous(report: Report, previous: dict[str, Any]) -> None:
    """Rellena `report.deltas` y `report.evolution` a partir del JSON anterior."""
    pr = report.pass_result
    intake = report.intake
    ignored: list[str] = []  # campos del JSON anterior con un tipo inesperado (se avisa, no se revienta)
    prev_scores = _scores_of(previous, ignored)
    prev_date = _date_of(previous, ignored)
    prev_global = _global_of(previous, ignored)
    current = pr.scores()

    header = f"- Pasada anterior: {previous['date'] if prev_date else 'fecha desconocida'}"
    if prev_global is not None:
        header += f" · score global {_global(prev_global)}"
    evolution = [header]
    warnings, objective_changed = _context_warnings(
        previous, prev_scores, prev_date, report.date, intake.stage.value, intake.objective
    )
    evolution.extend(f"- {w}" for w in warnings)

    for dim, score in current.items():
        report.deltas[dim] = _delta(prev_scores.get(dim), score, objective_changed)

    both = _both_scored(current, prev_scores)
    if objective_changed:
        moved = [f"{d.label} {fmt_score(p)} → {fmt_score(s)}" for d, p, s in both if s != p]
        if moved:
            evolution.append(
                "- Variaciones por dimensión (sin valorar, objetivo cambiado): " + "; ".join(moved) + "."
            )
    else:
        for dim, prev, score in both:
            if score < prev:
                evolution.append(
                    f"- 🔴 {dim.label} bajó {fmt_score(prev)} → {fmt_score(score)}. "
                    f"{_drop_cause(dim, pr.results[dim].findings, previous)}"
                )
        risen = [d.label for d, p, s in both if s > p]
        if risen:
            evolution.append(f"- Subieron: {', '.join(risen)}.")

    actions = _actions_of(previous, ignored)
    if actions:
        findings = [f for r in pr.results.values() for f in r.findings]
        open_texts = {_norm(f.text) for f in findings} | {_norm(f.action) for f in findings if f.action}
        gone = [a for a in actions if not a.keys & open_texts]
        evolution.append(
            f"- Acciones del roadmap anterior que ya no aparecen como hallazgo: {len(gone)}/{len(actions)} "
            "(candidatas a hechas; confirmar con el operador)."
        )
        evolution.extend(f"  - ✅? {a.text}" for a in gone)
        evolution.extend(f"  - ⏳ sigue abierta: {a.text}" for a in actions if a not in gone)
    if ignored:
        evolution.append(f"- {_ignored_line(ignored, 'anterior')}")
    report.evolution = evolution


# --- comparación entre dos informes guardados (`mvpup compare`) --------------------------------


@dataclass(frozen=True)
class DimensionDelta:
    dimension: Dimension
    previous: float | None
    current: float | None
    delta: str


@dataclass
class ReportDiff:
    product: str
    previous_date: str
    current_date: str
    previous_global: float | None
    current_global: float | None
    global_delta: str
    rows: list[DimensionDelta] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)  # en el roadmap anterior; ya ni acción ni hallazgo
    new: list[str] = field(default_factory=list)  # en el roadmap nuevo; antes ni acción ni hallazgo
    open: list[str] = field(default_factory=list)  # del roadmap anterior y siguen presentes
    warnings: list[str] = field(default_factory=list)


def _label_of(data: Mapping[str, Any]) -> str:
    product = data.get("product")
    if isinstance(product, str) and product.strip():
        return product
    slug = data.get("slug")
    return slug if isinstance(slug, str) and slug else "producto desconocido"


def diff_reports(previous: Mapping[str, Any], current: Mapping[str, Any]) -> ReportDiff:
    """Deltas por dimensión y acciones cerradas/nuevas/abiertas entre dos informes guardados.

    Función pura sobre los dos JSON gemelos; tolera campos corruptos (se avisan).
    """
    ignored_prev: list[str] = []
    ignored_cur: list[str] = []
    prev_scores = _scores_of(previous, ignored_prev)
    cur_scores = _scores_of(current, ignored_cur)
    prev_date = _date_of(previous, ignored_prev)
    cur_date = _date_of(current, ignored_cur)
    prev_global = _global_of(previous, ignored_prev)
    cur_global = _global_of(current, ignored_cur)
    cur_objective = _objective_of(current, ignored_cur)
    cur_stage = current.get("stage") if isinstance(current.get("stage"), str) else None

    warnings: list[str] = []
    if _label_of(previous) != _label_of(current):
        warnings.append(
            f"⚠️ Los informes son de productos distintos ({_label_of(previous)} / {_label_of(current)}): "
            "los Δ no significan evolución."
        )
    if prev_date and cur_date and cur_date < prev_date:
        warnings.append(
            f"⚠️ La pasada «nueva» ({cur_date}) es anterior a la pasada «anterior» ({prev_date}): "
            "¿argumentos en orden invertido?"
        )
    for which, data in (("anterior", previous), ("nuevo", current)):
        if data.get("dry_run"):
            warnings.append(f"⚠️ El informe {which} es un DRY-RUN (datos sintéticos): no es una auditoría.")
    context, objective_changed = _context_warnings(
        previous, prev_scores, prev_date, cur_date or date.today(), cur_stage, cur_objective
    )
    warnings.extend(context)

    order = list(Dimension)
    rows = [
        DimensionDelta(dim, prev_scores.get(dim), cur_scores.get(dim),
                       _delta(prev_scores.get(dim), cur_scores.get(dim), objective_changed))
        for dim in sorted(set(prev_scores) | set(cur_scores), key=order.index)
    ]
    if objective_changed and prev_global is not None and cur_global is not None:
        global_delta = f"n/c ({_global(prev_global)}→{_global(cur_global)})"
    else:
        global_delta = format_delta(prev_global, cur_global)

    prev_actions = _actions_of(previous, ignored_prev)
    cur_actions = _actions_of(current, ignored_cur)
    prev_present = _present(previous, prev_actions)
    cur_present = _present(current, cur_actions)

    if ignored_prev:
        warnings.append(_ignored_line(ignored_prev, "anterior"))
    if ignored_cur:
        warnings.append(_ignored_line(ignored_cur, "nuevo"))
    return ReportDiff(
        product=_label_of(current),
        previous_date=prev_date.isoformat() if prev_date else "fecha desconocida",
        current_date=cur_date.isoformat() if cur_date else "fecha desconocida",
        previous_global=prev_global,
        current_global=cur_global,
        global_delta=global_delta,
        rows=rows,
        closed=[a.text for a in prev_actions if not a.keys & cur_present],
        new=[a.text for a in cur_actions if not a.keys & prev_present],
        open=[a.text for a in prev_actions if a.keys & cur_present],
        warnings=warnings,
    )


def _score_cell(value: float | None) -> str:
    return "—" if value is None else f"{fmt_score(value)}/10"


def render_diff(diff: ReportDiff) -> str:
    """Resumen Markdown de la comparación (mismo estilo que el informe)."""
    lines = [
        f"# MVP-UP · Comparación · {diff.product}",
        "",
        f"**Pasada anterior:** {diff.previous_date} · score global {_global(diff.previous_global)}",
        f"**Pasada nueva:** {diff.current_date} · score global {_global(diff.current_global)}",
        f"**Δ score global:** {diff.global_delta}",
        "",
        "## Δ por dimensión",
        "",
        "| Dimensión | Anterior | Nueva | Δ |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r.dimension.label} | {_score_cell(r.previous)} | {_score_cell(r.current)} | {r.delta} |"
        for r in diff.rows
    ] or ["| — | — | — | — |"]
    lines += ["", "## Acciones cerradas (candidatas a hechas; confirmar con el operador)"]
    lines += [f"- ✅? {a}" for a in diff.closed] or ["- Ninguna."]
    lines += ["", "## Acciones nuevas"]
    lines += [f"- 🆕 {a}" for a in diff.new] or ["- Ninguna."]
    lines += ["", "## Acciones que siguen abiertas"]
    lines += [f"- ⏳ {a}" for a in diff.open] or ["- Ninguna."]
    if diff.warnings:
        lines += ["", "## Avisos"]
        lines += [f"- {w}" for w in diff.warnings]
    lines += ["", "> Una acción «cerrada» solo deja de aparecer como hallazgo: el operador confirma si se hizo."]
    return "\n".join(lines) + "\n"
