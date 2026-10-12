"""Fase 5 · Informe versionado (Markdown + JSON gemelo para comparar pasadas).

El Markdown conserva los headers EXACTOS de skill/references/plantilla-informe.md
(el orquestador no condensa ni reinventa el formato). El JSON gemelo es la fuente
estructurada que lee la comparación de la siguiente pasada.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .compare import compare_with_previous
from .consolidation import Entry, Quadrant, Structural, build_matrix, structural_findings
from .dimensions import Dimension, Mode
from .intake import Intake
from .orchestrator import PassResult
from .runners import AgentUsage
from .parsing import LIGERA_TEMPLATE, shorten
from .roadmap import HORIZON_RULE_NOTE, Horizon, Roadmap, RoadmapItem, build_roadmap, top_five
from .scoring import fmt_score, global_score, status_icon

SCHEMA_VERSION = 1

# Nombre exacto de un informe: YYYY-MM-DD-informe[-N] (cualquier otro fichero se ignora).
REPORT_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-informe(?:-(\d+))?\Z")


@dataclass
class Report:
    pass_result: PassResult
    date: date
    pass_number: int
    global_score: float | None
    matrix: dict[Quadrant, list[Entry]] = field(default_factory=dict)
    structural: list[Structural] = field(default_factory=list)
    roadmap: Roadmap = field(default_factory=Roadmap)
    top: list[str] = field(default_factory=list)
    evolution: list[str] = field(default_factory=list)
    deltas: dict[Dimension, str] = field(default_factory=dict)
    dry_run: bool = False  # datos sintéticos: nunca es una auditoría ni cuenta como pasada

    @property
    def intake(self) -> Intake:
        return self.pass_result.intake


DRY_RUN_NOTICE = (
    "**⚠️ DRY-RUN:** agentes simulados con datos sintéticos (evidencias marcadas "
    "`[sintético]`). Este informe NO es una auditoría y no cuenta como pasada."
)


def slugify(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    if not slug:
        raise ValueError(f"el nombre {name!r} no produce un identificador válido")
    return slug


def report_dir(base_dir: Path | str, product: str) -> Path:
    """Carpeta del producto dentro de `base_dir`; el slug impide salir de ella."""
    return Path(base_dir) / slugify(product)


def previous_reports(base_dir: Path | str | None, product: str) -> list[Path]:
    """Pasadas anteriores (una ruta sin extensión por pasada), de la más antigua a la más reciente.

    El Markdown es el informe canónico: solo los `.md` cuentan como pasada (tengan o
    no JSON gemelo); un `.json` sin su `.md` es un resto huérfano y se ignora.
    """
    if base_dir is None:
        return []
    folder = report_dir(base_dir, product)
    if not folder.is_dir():
        return []
    stems = (p.with_suffix("") for p in folder.glob("*-informe*.md"))
    return sorted((p for p in stems if REPORT_NAME_RE.match(p.name)), key=report_sort_key)


def report_sort_key(path: Path) -> tuple[str, int]:
    m = REPORT_NAME_RE.match(path.stem)
    if not m:
        return (path.stem, 0)
    return (m.group(1), int(m.group(2) or 1))


def build_report(
    pass_result: PassResult,
    today: date | None = None,
    base_dir: Path | str | None = None,
    dry_run: bool = False,
) -> Report:
    """`dry_run`: datos sintéticos; no se compara con pasadas anteriores ni las cuenta."""
    intake = pass_result.intake
    today = today or date.today()
    if dry_run:
        base_dir = None
    number = len(previous_reports(base_dir, intake.product)) + 1
    if intake.mode is Mode.LIGERA:
        score = pass_result.ligera.score if pass_result.ligera else None
        return Report(pass_result, today, number, score, dry_run=dry_run)
    matrix = build_matrix(pass_result.results, intake.objective)
    structural = structural_findings(pass_result.results)
    roadmap = build_roadmap(
        matrix, intake.objective, in_wip_lanes=intake.in_wip_lanes, structural=structural
    )
    report = Report(
        pass_result=pass_result,
        date=today,
        pass_number=number,
        global_score=global_score(pass_result.scores(), intake.objective),
        matrix=matrix,
        structural=structural,
        roadmap=roadmap,
        top=top_five(roadmap),
        dry_run=dry_run,
    )
    previous = previous_reports(base_dir, intake.product)
    if previous:
        last = previous[-1].with_suffix(".json")
        if not last.exists():
            report.evolution = [
                f"- ⚠️ Pasada anterior {previous[-1].name}.md sin JSON gemelo: "
                "comparación automática no disponible (compararla a mano)."
            ]
            return report
        try:
            data = json.loads(last.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("el JSON no es un objeto")
        except (OSError, ValueError) as exc:
            report.evolution = [
                f"- ⚠️ Informe anterior ilegible ({last.name}: {exc}); sin comparación."
            ]
        else:
            try:
                compare_with_previous(report, data)
            except Exception as exc:  # noqa: BLE001 — la comparación es accesoria: el informe, no
                report.evolution = [
                    f"- ⚠️ La comparación automática con {last.name} falló "
                    f"({type(exc).__name__}: {exc}); compararla a mano."
                ]
    return report


MATRIX_ITEM_CHARS = 80  # una línea corta por ítem de la matriz; el detalle vive en el roadmap


def _entry(e: Entry) -> str:
    """Hallazgo completo con su dimensión y evidencia (el detalle del informe)."""
    return f"{e.finding.text} ({e.dimension.label} · Evidencia: {e.finding.evidence})"


def _entry_with_action(e: Entry) -> str:
    """Detalle de un hallazgo que NO se programa, con la acción que proponía el agente."""
    action = f" · acción propuesta: {e.finding.action}" if e.finding.action else ""
    return _entry(e) + action


def _cell_item(e: Entry) -> str:
    """Ítem de la matriz: la acción (o el hallazgo abreviado) y su dimensión, en una línea."""
    return f"{shorten(e.finding.label, MATRIX_ITEM_CHARS)} ({e.dimension.label})"


def _cell(entries: list[Entry]) -> str:
    return "<br>".join(_cell_item(e).replace("|", "\\|") for e in entries) or "—"


def _scores_table(report: Report) -> list[str]:
    pr = report.pass_result
    rows = ["| Dimensión | Score | Δ vs anterior | Estado |", "|---|---|---|---|"]
    for dim in Dimension:
        delta = report.deltas.get(dim, "—")
        if dim in pr.results:
            s = pr.results[dim].score
            # El semáforo se calcula sobre el score TAL COMO SE MUESTRA (1 decimal): un 6,96
            # se imprime «7,0» y debe ser 🟢, no 🟡, o la leyenda miente.
            rows.append(f"| {dim.label} | {fmt_score(s)}/10 | {delta} | {status_icon(round(s, 1))} |")
        elif dim in pr.unevaluated:
            rows.append(f"| {dim.label} | sin evaluar | {delta} | ⚪ |")
        elif dim in pr.not_applicable:
            rows.append(f"| {dim.label} | N/A | — | ⚪ |")
    rows.append("")
    rows.append("🟢 7-10 · 🟡 5-6 · 🔴 0-4 · ⚪ N/A")
    return rows


def _roadmap_item_line(i: RoadmapItem) -> str:
    """Una acción del roadmap. Coste y ejecutor solo se imprimen si se conocen."""
    parts = [i.entry.finding.label]
    if i.has_cost:
        parts.append(f"~{i.cost}")
    parts.append(f"sube {i.dimension_labels}")
    if i.has_owner:
        parts.append(f"ejecutable por: {i.owner}")
    if i.queued:
        parts.append("encolar")
    return "- [ ] " + " · ".join(parts)


def _roadmap_context_lines(i: RoadmapItem) -> list[str]:
    """El detalle de la acción: el hallazgo que la motiva y su evidencia.

    Sin acción (informes/parsers antiguos) la línea ya ES el hallazgo: solo falta su evidencia.
    """
    lines = []
    for e in (i.entry, *i.related):
        if e is i.entry and not e.finding.action:
            lines.append(f"  - Evidencia: {e.finding.evidence}")
        else:
            lines.append(f"  - Hallazgo: {_entry(e)}")
    return lines


def _unknowns_line(roadmap: Roadmap) -> str | None:
    """Cuántas acciones programadas carecen de coste o ejecutor: se dice UNA vez, no en cada línea."""
    items = roadmap.all_items()
    no_cost = sum(1 for i in items if not i.has_cost)
    no_owner = sum(1 for i in items if not i.has_owner)
    if not (no_cost or no_owner):
        return None
    return (
        f"ℹ️ {no_cost} de {len(items)} acciones sin coste estimado · {no_owner} de {len(items)} sin "
        "ejecutor asignado: ni los agentes ni el operador los aportaron, y no se inventan."
    )


def _roadmap_lines(roadmap: Roadmap, discarded: list[Entry]) -> list[str]:
    out: list[str] = [HORIZON_RULE_NOTE, ""]
    for h in Horizon:
        out.append(f"### {h.value} — {h.label}")
        items = roadmap.items(h)
        if not items:
            out.append("- (sin acciones)")
        for i in items:
            out.append(_roadmap_item_line(i))
            out.extend(_roadmap_context_lines(i))
        out.append("")
    unknowns = _unknowns_line(roadmap)
    if unknowns:
        out += [unknowns, ""]
    if roadmap.backlog:
        out.append("Backlog «si sobra tiempo» (impacto bajo, no programado):")
        out.extend(f"- {_entry_with_action(i.entry)}" for i in roadmap.backlog)
        out.append("")
    if roadmap.not_justified:
        out.append("Apuestas no justificadas por el objetivo de valor (no se programan):")
        out.extend(f"- {_entry_with_action(i.entry)}" for i in roadmap.not_justified)
        out.append("")
    if discarded:
        out.append("Descartado por la matriz (impacto medio/bajo con esfuerzo medio/alto; no se programa):")
        out.extend(f"- {_entry_with_action(e)}" for e in discarded)
        out.append("")
    if roadmap.wip_note:
        out.append(f"⚠️ Nota WIP: {roadmap.wip_note}")
        out.append("")
    return out


def _missing_data_lines(pr: PassResult) -> list[str]:
    """Un dato pedido por varias dimensiones aparece una vez, con todas ellas."""
    asked: dict[str, list[str]] = {}
    for dim in Dimension:
        if dim in pr.results:
            for item in pr.results[dim].missing_data:
                labels = asked.setdefault(item, [])
                if dim.label not in labels:
                    labels.append(dim.label)
    return [f"- {item} ({', '.join(dims)})" for item, dims in asked.items()]


def _discarded_lines(pr: PassResult) -> list[str]:
    """Hallazgos que el agente citó sin evidencia: el operador debe saber que se quitaron."""
    return [
        f"- {dim.label}: {w} (el agente lo afirmó sin prueba; aportar evidencia o re-evaluar)"
        for dim in Dimension
        if dim in pr.results
        for w in pr.results[dim].warnings
    ]


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _ordered_usage(pr: PassResult) -> dict[str, AgentUsage]:
    """Consumo en el orden del plan (los agentes terminan en el orden que quieren los hilos)."""
    planned = [t.key for t in pr.plan.tasks if t.key in pr.usage]
    rest = sorted(k for k in pr.usage if k not in planned)
    return {key: pr.usage[key] for key in (*planned, *rest)}


def usage_summary(pr: PassResult) -> dict[str, Any] | None:
    """Consumo de la pasada para el JSON: por agente, total y modelos. None si el runner no informa."""
    usage = _ordered_usage(pr)
    if not usage:
        return None
    agents = {
        key: {"model": u.model, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens, "calls": u.calls}
        for key, u in usage.items()
    }
    return {
        "agents": agents,
        "total": {
            "input_tokens": sum(u.input_tokens for u in usage.values()),
            "output_tokens": sum(u.output_tokens for u in usage.values()),
            "calls": sum(u.calls for u in usage.values()),
        },
        "models": sorted({u.model for u in usage.values()}),
    }


def usage_line(pr: PassResult) -> str | None:
    """Una línea con el consumo. Solo tokens: los precios cambian, el importe no se calcula."""
    summary = usage_summary(pr)
    if summary is None:
        return None
    total = summary["total"]
    calls = total["calls"]
    per_agent = " · ".join(
        f"{key} {_thousands(u['input_tokens'])}/{_thousands(u['output_tokens'])}"
        for key, u in summary["agents"].items()
    )
    return (
        f"**Consumo:** {_thousands(total['input_tokens'])} tokens de entrada · "
        f"{_thousands(total['output_tokens'])} de salida · {calls} llamada{'s' if calls != 1 else ''} · "
        f"modelo {', '.join(summary['models'])} (por agente, entrada/salida: {per_agent})"
    )


def _header_lines(report: Report) -> list[str]:
    it = report.intake
    lines = [
        f"# MVP-UP · {it.product} · {report.date.isoformat()}",
        "",
        f"**Modo:** {it.mode.value} · **Etapa:** {it.stage.value} · "
        f"**Objetivo de valor:** {it.objective.value}",
    ]
    consumption = usage_line(report.pass_result)
    if consumption:
        lines.append(consumption)
    supplied = len(it.operator_context.strip())
    if supplied:
        # Solo consta QUE se aportó: el texto no se copia al informe.
        lines.append(
            f"**Contexto del operador:** aportado ({_thousands(supplied)} caracteres, adjunto a todos "
            "los agentes como dato no verificado)"
        )
    if report.dry_run:
        lines.insert(2, DRY_RUN_NOTICE)
    return lines


def render_markdown(report: Report) -> str:
    if report.intake.mode is Mode.LIGERA:
        return _render_ligera(report)
    pr = report.pass_result
    m = report.matrix
    lines = _header_lines(report)
    lines.append(
        f"**Score global: {fmt_score(report.global_score, 1)}/10** (ponderado por objetivo) · "
        f"Pasada nº {report.pass_number}"
    )
    lines += ["", "## Scores por dimensión", ""] + _scores_table(report)
    lines += ["", "## Hallazgos estructurales"]
    if report.structural:
        for s in report.structural:
            dims = " + ".join(d.label for d in s.dimensions)
            lines.append(f"- {s.label} — bloquea: {dims}")
            lines.extend(f"  - {_entry(e)}" for e in s.entries)
    else:
        lines.append("- Ninguno detectado entre dimensiones.")
    lines += [
        "",
        "## Matriz impacto × esfuerzo",
        "",
        "|  | Esfuerzo BAJO | Esfuerzo MEDIO/ALTO |",
        "|---|---|---|",
        f"| **Impacto ALTO** | ⚡ QUICK WINS: {_cell(m[Quadrant.QUICK_WINS])} | "
        f"🎯 APUESTAS: {_cell(m[Quadrant.APUESTAS])} |",
        f"| **Impacto MEDIO/BAJO** | 📋 Si sobra tiempo: {_cell(m[Quadrant.SI_SOBRA_TIEMPO])} | "
        f"🗑️ Descartar: {_cell(m[Quadrant.DESCARTAR])} |",
        "",
        "## Roadmap de escalado",
        "",
    ]
    lines += _roadmap_lines(report.roadmap, m[Quadrant.DESCARTAR])
    lines.append("## Evolución (solo si hay pasada anterior)")
    lines += report.evolution or ["- Primera pasada: este informe es la línea base."]
    lines += ["", "## Datos pendientes que el operador debe aportar"]
    missing = _missing_data_lines(pr) + _discarded_lines(pr)
    if pr.unevaluated:
        missing.append(
            "- Re-evaluar: " + ", ".join(d.label for d in pr.unevaluated) + " (sin evaluar en esta pasada)"
        )
    lines += missing or ["- Ninguno."]
    lines += ["", "## TOP-5 propuesto para autorización"]
    lines += [f"{n}. {t}" for n, t in enumerate(report.top, 1)] or ["- Sin acciones propuestas."]
    lines += ["", "> Diagnóstico: nada se ejecuta hasta que el operador autorice el TOP-5."]
    return "\n".join(lines) + "\n"


def _render_ligera(report: Report) -> str:
    h = dict(LIGERA_TEMPLATE)
    lines = _header_lines(report) + [f"Pasada nº {report.pass_number} · modo ligera", ""]
    lig = report.pass_result.ligera
    if lig is None:
        lines.append("⚠️ El agente ligera no devolvió un formato válido tras el reintento: sin evaluar.")
        return "\n".join(lines) + "\n"
    lines.append(h["score"].replace("X/10", f"{fmt_score(lig.score)}/10"))
    lines += [h["state"], lig.state or "N/D", "", h["findings"]]
    lines += [
        f"- [{f.id}] {f.text} · Impacto: {f.impact.value} · Evidencia: {f.evidence}"
        for f in lig.findings
    ]
    lines += [f"- ⚠️ {w} (el agente lo afirmó sin prueba)" for w in lig.warnings]
    lines += ["", h["value"], lig.value or "N/D", "", h["resume"]]
    lines += [f"{n}. {t}" for n, t in enumerate(lig.resume_tasks, 1)]
    return "\n".join(lines) + "\n"


def to_json(report: Report) -> dict[str, Any]:
    pr = report.pass_result
    it = report.intake
    data: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "product": it.product,
        "slug": slugify(it.product),
        "date": report.date.isoformat(),
        "mode": it.mode.value,
        "stage": it.stage.value,
        "objective": it.objective.value,
        "pass_number": report.pass_number,
        "dry_run": report.dry_run,
        "global_score": report.global_score,
        "scores": {d.value: s for d, s in pr.scores().items()},
        "not_applicable": [d.value for d in pr.not_applicable],
        "unevaluated": [d.value for d in pr.unevaluated],
        "roadmap": [
            {
                "horizon": i.horizon.value,
                "dimension": i.entry.dimension.value,
                "dimensions": [d.value for d in i.dimensions],
                "action": i.entry.finding.label,
                "finding": i.entry.finding.text,
                "finding_id": i.entry.finding.id,
                "cost": i.cost if i.has_cost else None,
                "owner": i.owner if i.has_owner else None,
            }
            for i in report.roadmap.all_items()
        ],
        "findings": [
            {
                "dimension": d.value,
                "id": f.id,
                "text": f.text,
                "action": f.action or None,
                "impact": f.impact.value,
                "effort": f.effort.value if f.effort else None,
                "evidence": f.evidence,
            }
            for d in Dimension
            if d in pr.results
            for f in pr.results[d].findings
        ],
        "top": report.top,
        "usage": usage_summary(pr),
        "operator_context": (
            {"provided": True, "chars": len(it.operator_context.strip())}
            if it.operator_context.strip() else None
        ),
        "log": pr.log,
    }
    return data


def save_report(report: Report, base_dir: Path | str) -> Path:
    """Escribe `<base>/<slug>/YYYY-MM-DD-informe[-N].md` + `.json`. Nunca sobrescribe.

    Un dry-run se guarda como `YYYY-MM-DD-dry-run[-N]`: ese nombre no cumple
    `REPORT_NAME_RE`, así que ni la siguiente pasada ni la cartera lo ven.
    """
    folder = report_dir(base_dir, report.intake.product)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{report.date.isoformat()}-{'dry-run' if report.dry_run else 'informe'}"
    n = 1
    path = folder / f"{stem}.md"
    while path.exists() or path.with_suffix(".json").exists():
        n += 1
        path = folder / f"{stem}-{n}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(to_json(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
