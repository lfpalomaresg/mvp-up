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

from .compare import compare_with_previous
from .consolidation import Entry, Quadrant, Structural, build_matrix, structural_findings
from .dimensions import Dimension, Mode
from .intake import Intake
from .orchestrator import PassResult
from .parsing import LIGERA_TEMPLATE
from .roadmap import Horizon, Roadmap, build_roadmap, top_five
from .scoring import global_score, status_icon

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


def fmt_score(score: float | None, decimals: int | None = None) -> str:
    if score is None:
        return "—"
    if decimals is None:
        decimals = 0 if float(score).is_integer() else 1
    return f"{score:.{decimals}f}".replace(".", ",")


def _entry(e: Entry) -> str:
    return f"{e.finding.text} ({e.dimension.label} · Evidencia: {e.finding.evidence})"


def _cell(entries: list[Entry]) -> str:
    return "<br>".join(_entry(e).replace("|", "\\|") for e in entries) or "—"


def _scores_table(report: Report) -> list[str]:
    pr = report.pass_result
    rows = ["| Dimensión | Score | Δ vs anterior | Estado |", "|---|---|---|---|"]
    for dim in Dimension:
        delta = report.deltas.get(dim, "—")
        if dim in pr.results:
            s = pr.results[dim].score
            rows.append(f"| {dim.label} | {fmt_score(s)}/10 | {delta} | {status_icon(s)} |")
        elif dim in pr.unevaluated:
            rows.append(f"| {dim.label} | sin evaluar | {delta} | ⚪ |")
        elif dim in pr.not_applicable:
            rows.append(f"| {dim.label} | N/A | — | ⚪ |")
    rows.append("")
    rows.append("🟢 7-10 · 🟡 5-6 · 🔴 0-4 · ⚪ N/A")
    return rows


def _roadmap_lines(roadmap: Roadmap) -> list[str]:
    out: list[str] = []
    for h in Horizon:
        out.append(f"### {h.value} — {h.label}")
        items = roadmap.items(h)
        if not items:
            out.append("- (sin acciones)")
        for i in items:
            tail = " · encolar" if i.queued else ""
            out.append(
                f"- [ ] {i.entry.finding.text} · ~{i.cost} · sube {i.dimension_labels} · "
                f"ejecutable por: {i.owner}{tail}"
            )
        out.append("")
    if roadmap.backlog:
        out.append("Backlog «si sobra tiempo» (impacto bajo, no programado):")
        out.extend(f"- {_entry(i.entry)}" for i in roadmap.backlog)
        out.append("")
    if roadmap.not_justified:
        out.append("Apuestas no justificadas por el objetivo de valor (no se programan):")
        out.extend(f"- {_entry(i.entry)}" for i in roadmap.not_justified)
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


def _header_lines(report: Report) -> list[str]:
    it = report.intake
    lines = [
        f"# MVP-UP · {it.product} · {report.date.isoformat()}",
        "",
        f"**Modo:** {it.mode.value} · **Etapa:** {it.stage.value} · "
        f"**Objetivo de valor:** {it.objective.value}",
    ]
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
    lines += _roadmap_lines(report.roadmap)
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


def to_json(report: Report) -> dict:
    pr = report.pass_result
    it = report.intake
    data = {
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
                "action": i.entry.finding.text,
            }
            for i in report.roadmap.all_items()
        ],
        "findings": [
            {
                "dimension": d.value,
                "id": f.id,
                "text": f.text,
                "impact": f.impact.value,
                "effort": f.effort.value if f.effort else None,
                "evidence": f.evidence,
            }
            for d in Dimension
            if d in pr.results
            for f in pr.results[d].findings
        ],
        "top": report.top,
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


ANCHOR_TITLE = "## ⚡ MVP-UP {score}/10 ({date}) — LEER AL RETOMAR"


def anchor_ficha(
    ficha: Path,
    report_path: Path,
    score: float | None,
    when: date,
    product: str | None = None,
    repo: str | None = None,
) -> bool:
    """Fase 5.2: añade el anclaje «salta al retomar» al final de la ficha (idempotente).

    Si la ficha no existe se crea la mínima (qué es / estado / repo / informe). Devuelve True
    si escribió algo; un mismo informe no se ancla dos veces. Nunca reescribe contenido existente: solo añade al final.
    """
    title = ANCHOR_TITLE.format(score=fmt_score(score, 1) if score is not None else "—", date=when.isoformat())
    pointer = f"Informe: `{report_path}`"
    block = f"\n{title}\n{pointer} — la próxima sesión sobre este producto arranca leyéndolo.\n"
    if ficha.exists():
        text = ficha.read_text(encoding="utf-8")
        if pointer in text:  # idempotente por INFORME, no por fecha/score
            return False
        ficha.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
        return True
    ficha.parent.mkdir(parents=True, exist_ok=True)
    name = product or ficha.stem
    ficha.write_text(
        f"# {name}\n\n- Qué es: N/D (completar)\n- Estado: auditado con MVP-UP\n"
        f"- Repo: `{repo or 'N/D'}`\n- Informe: `{report_path}`\n{block}",
        encoding="utf-8",
    )
    return True
