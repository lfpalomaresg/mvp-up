"""Síntesis de CARTERA (SKILL.md Fase 2.5): patrones transversales entre proyectos.

Lee el último informe JSON de cada producto en la carpeta de informes y busca lo
que ningún informe individual muestra: dimensiones débiles en toda la cartera,
dominancias sistemáticas (p.ej. «técnica siempre > comercial») y huecos de
medición repetidos. Determinista; el orquestador decide qué hacer con ello.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from itertools import permutations
from pathlib import Path
from typing import Any

from .dimensions import Dimension
from .report import REPORT_NAME_RE, SCHEMA_VERSION, report_sort_key
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

WEAK_THRESHOLD = 4  # ≤4 = deficiente según la rúbrica común


@dataclass
class Portfolio:
    reports: list[dict[str, Any]]
    # Ranking por score global DENTRO de cada objetivo (pesos distintos no se comparan).
    ranking_by_objective: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    patterns: list[str] = field(default_factory=list)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_report(data: Any) -> bool:
    """Esquema mínimo: si algo no cuadra, el informe se descarta (se usa el anterior)."""
    if not isinstance(data, dict) or not isinstance(data.get("scores"), dict):
        return False
    if data.get("dry_run"):  # datos sintéticos: jamás entran en la cartera
        return False
    schema = data.get("schema")
    if type(schema) is not int or schema != SCHEMA_VERSION:  # `True == 1` no cuela
        return False
    if not isinstance(data.get("objective"), str) or "global_score" not in data:
        return False
    if not isinstance(data.get("date"), str) or not _DATE_RE.match(data["date"]):
        return False
    gs = data.get("global_score")
    if gs is not None and not (_is_number(gs) and 0 <= gs <= 10):
        return False
    return all(v is None or (_is_number(v) and 0 <= v <= 10) for v in data["scores"].values())


def load_latest_reports(base_dir: Path | str) -> list[dict[str, Any]]:
    """Último informe legible de cada producto (subcarpeta) de `base_dir`."""
    latest: list[dict[str, Any]] = []
    for folder in sorted(p for p in Path(base_dir).iterdir() if p.is_dir()):
        candidates = [p for p in folder.glob("*-informe*.json") if REPORT_NAME_RE.match(p.stem)]
        for path in sorted(candidates, key=report_sort_key, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if _valid_report(data):
                data.setdefault("slug", folder.name)
                latest.append(data)
                break
    return latest


def _score(report: dict[str, Any], dim: Dimension) -> float | None:
    value = report["scores"].get(dim.value)
    return float(value) if _is_number(value) else None


def synthesize(reports: list[dict[str, Any]]) -> Portfolio:
    if len(reports) < 2:
        raise ValueError("la síntesis de cartera necesita al menos 2 proyectos")
    n = len(reports)
    portfolio = Portfolio(reports=reports)
    def rank_key(r: dict[str, Any]) -> tuple[bool, float, str]:
        gs = r.get("global_score")
        return (gs is None, -gs if gs is not None else 0.0, r.get("slug", ""))

    for r in sorted(reports, key=rank_key):
        portfolio.ranking_by_objective.setdefault(r.get("objective") or "N/D", []).append(r)
    portfolio.ranking_by_objective = dict(sorted(portfolio.ranking_by_objective.items()))
    patterns = portfolio.patterns

    if len(portfolio.ranking_by_objective) > 1:
        patterns.append(
            f"⚠️ Proyectos con objetivos de valor distintos ({', '.join(portfolio.ranking_by_objective)}): "
            "los scores globales solo se comparan dentro de cada objetivo."
        )

    unmeasured_elsewhere: list[str] = []
    for dim in Dimension:
        evaluated = [s for r in reports if (s := _score(r, dim)) is not None]
        unmeasured = n - len(evaluated)  # ausente del informe o «sin evaluar»
        if evaluated and all(s <= WEAK_THRESHOLD for s in evaluated):
            if len(evaluated) >= 2 and len(evaluated) * 2 > n:
                patterns.append(
                    f"{dim.label}: débil en toda la cartera ({len(evaluated)}/{n} proyectos "
                    f"evaluados, todos ≤{WEAK_THRESHOLD}) — hueco transversal, no de un proyecto."
                )
            else:
                patterns.append(
                    f"{dim.label}: débil donde se evaluó ({len(evaluated)}/{n}), pero la cobertura "
                    "no basta para llamarlo transversal."
                )
        if unmeasured >= 2 and unmeasured * 2 > n:
            if dim is Dimension.DATOS:
                patterns.append(
                    f"{dim.label}: sin medir en {unmeasured}/{n} proyectos — sin esta dimensión "
                    "los Δ entre auditorías son opinión (punto ciego de la cartera)."
                )
            else:
                unmeasured_elsewhere.append(f"{dim.label} ({unmeasured}/{n})")
    if unmeasured_elsewhere:
        patterns.append(
            "Sin medir en la mayoría de proyectos: " + ", ".join(unmeasured_elsewhere)
            + " (en express puede ser por diseño de la etapa)."
        )

    for a, b in permutations(Dimension, 2):
        pairs = [(sa, sb) for r in reports
                 if (sa := _score(r, a)) is not None and (sb := _score(r, b)) is not None]
        if len(pairs) >= 2 and len(pairs) == n and all(sa > sb for sa, sb in pairs):
            patterns.append(
                f"{a.label} > {b.label} en {len(pairs)}/{n} proyectos: sesgo sistemático "
                "de dónde se invierte el esfuerzo."
            )
    return portfolio


def _fmt(value: Any) -> str:
    return f"{float(value):.1f}".replace(".", ",") + "/10" if isinstance(value, (int, float)) else "—"


def render_portfolio(portfolio: Portfolio) -> str:
    lines = [
        "# MVP-UP · Síntesis de cartera",
        "",
        f"Proyectos: {len(portfolio.reports)} (último informe de cada uno)",
        "",
        "## Ranking por score global",
    ]
    grouped = len(portfolio.ranking_by_objective) > 1
    for objective, ranked in portfolio.ranking_by_objective.items():
        if grouped:
            lines += ["", f"### Objetivo: {objective}"]
        lines += ["", "| Proyecto | Score global | Fecha |", "|---|---|---|"]
        lines += [
            f"| {r.get('product', r.get('slug'))} | {_fmt(r.get('global_score'))} | {r.get('date', '—')} |"
            for r in ranked
        ]
    lines += ["", "## Cobertura por dimensión", "", "| Dimensión | Evaluada en |", "|---|---|"]
    n = len(portfolio.reports)
    for dim in Dimension:
        k = sum(1 for r in portfolio.reports if _score(r, dim) is not None)
        lines.append(f"| {dim.label} | {k}/{n} |")
    lines += ["", "## Patrones transversales"]
    lines += [f"- {p}" for p in portfolio.patterns] or ["- Ninguno detectado."]
    lines += ["", "> Diagnóstico de cartera: candidatos a revisar por el operador, no conclusiones."]
    return "\n".join(lines) + "\n"
