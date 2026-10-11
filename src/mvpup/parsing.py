"""Validador de formato y parser de la salida de los agentes.

Regla de la skill: el output DEBE contener los headers `##` exactos de su
plantilla (completa o ligera). Si falta alguno, o el contenido viola la
plantilla (score fuera de rango, más de 7 hallazgos), es formato inválido y el
orquestador reintenta una vez. Regla del informe: hallazgo sin evidencia → fuera.

"Exacto" tolera solo una cosa: omitir la aclaración entre paréntesis de la
plantilla (`## Hallazgos` vale por `## Hallazgos (máx 7, ordenados por impacto)`).
Cualquier otro texto añadido al header lo invalida.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from .dimensions import MAX_FINDINGS, Dimension


class FormatError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


class Level(str, Enum):
    ALTO = "A"
    MEDIO = "M"
    BAJO = "B"


# (clave interna, header EXACTO de la plantilla). Se acepta también el header
# sin su aclaración final entre paréntesis, y nada más.
Template = tuple[tuple[str, str], ...]

FULL_TEMPLATE: Template = (
    ("score", "## Score: X/10 (rúbrica al pie)"),
    ("findings", "## Hallazgos (máx 7, ordenados por impacto)"),
    ("quick_wins", "## Quick wins (impacto A/M con esfuerzo B)"),
    ("risks", "## Riesgos si no se actúa"),
    ("missing", "## Datos que faltan para evaluar mejor"),
)

LIGERA_TEMPLATE: Template = (
    ("score", "## Score orientativo: X/10"),
    ("state", "## Qué es y estado real (3-4 líneas: qué hay construido DE VERDAD vs lo que dice la ficha)"),
    ("findings", "## Hallazgos clave (3-5, con evidencia)"),
    ("value", "## Valor potencial (1-2 líneas: a qué objetivo del operador sirve — o si conviene archivarla)"),
    ("resume", "## 3 tareas de reanudación (lo primero al retomar, concretas y ordenadas — o de CIERRE si recomienda archivar)"),
)

# Línea que separa los bloques de un agente que cubre 2 dimensiones agrupadas.
GROUP_SEPARATOR = "# Dimensión: "
# Lo que se ACEPTA al leer: también sin tilde, en mayúsculas o con espacios de más.
_SEPARATOR_RE = re.compile(r"^#\s*dimensi[oó]n\s*:\s*(?P<ident>.+?)\s*$", re.IGNORECASE)

# El signo se admite solo para poder decir «fuera de rango» en vez de «header ausente».
_SCORE_NUM = r"(-?\d+(?:[.,]\d+)?)\s*/\s*10"
# Un separador agrupado escrito como `## Dimensión:` (nivel equivocado): se explica, no se adivina.
_H2_SEPARATOR_RE = re.compile(r"^##\s*dimensi[oó]n\s*:", re.IGNORECASE)
_PAREN_TAIL_RE = re.compile(r"\s*\([^()]*\)$")
_FINDING_RE = re.compile(
    # Nivel: la sigla de la plantilla (A/M/B) o la palabra completa (Alto/Medio/Bajo).
    r"^[-*]\s*\[(?P<id>H\d+)\]\s*(?P<text>.+?)\s*[·|]\s*Impacto:\s*(?P<imp>Alto|Medio|Bajo|[AMB])\b"
    r"(?:\s*[·|]\s*Esfuerzo:\s*(?P<eff>Alto|Medio|Bajo|[AMB])\b)?"
    r"(?:\s*[·|]\s*Evidencia:\s*(?P<ev>.*))?$",
    re.IGNORECASE,
)
# Evidencia que en realidad declara su ausencia ("N/D (no comprobado)", "sin evidencia...").
_NO_EVIDENCE_RE = re.compile(
    r"^(?:n\s*/?\s*d\b|n/a\b|sin evidencia|ninguna\b|no (?:verificad|comprobad|disponible)|[-—–]+$|$)",
    re.IGNORECASE,
)
# Una línea que EMPIEZA por `[Hn]` pretende ser un hallazgo: si no se lee, es fallo de
# formato (reintento), nunca un descarte silencioso. Delante se admite cualquier marcador
# no alfanumérico (viñeta, negrita, espacios) o un enumerador corto (`2.`, `IV)`, `a)`).
# La prosa que solo cita un hallazgo («Resumen: priorizar [H1]…») no lo es.
# Sin cuantificador anidado sobre runs (`(X+)*`): una iteración por carácter → sin backtracking exponencial.
_FINDING_LIKE_RE = re.compile(r"^(?:[^\w\[]|\w{1,3}[.)])*\[H\d+\]", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    id: str
    text: str
    impact: Level
    effort: Level | None
    evidence: str


@dataclass
class DimensionResult:
    score: float
    findings: list[Finding]
    quick_wins: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class LigeraResult:
    score: float
    state: str
    findings: list[Finding]
    value: str
    resume_tasks: list[str]
    warnings: list[str] = field(default_factory=list)


def _header_forms(header: str) -> tuple[str, ...]:
    """Formas aceptadas del header: completa y sin su paréntesis final."""
    short = _PAREN_TAIL_RE.sub("", header)
    return (header, short) if short != header else (header,)


@lru_cache(maxsize=None)
def _header_regex(header: str) -> re.Pattern[str]:
    alternatives = []
    for form in _header_forms(header):
        alternatives.append(re.escape(form).replace(re.escape("X/10"), _SCORE_NUM))
    # Si la forma no lleva score, el grupo 1 no existe: lo normalizamos con `(?:)`.
    pattern = "|".join(f"(?:{a})" for a in alternatives)
    return re.compile(rf"^(?:{pattern})$")


def _match_header(line: str, header: str) -> re.Match[str] | None:
    return _header_regex(header).match(line)


def _lines(text: str) -> list[str]:
    """Líneas del texto sin el BOM inicial (algunos clientes lo anteponen)."""
    return text.lstrip("﻿").splitlines()


def _sections(text: str, template: Template) -> dict[str, list[str]]:
    """Trocea por headers `##` de la plantilla; un header desconocido corta la sección."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in _lines(text):
        line = raw.strip()
        if re.match(r"^##(?!#)", line):
            current = next((k for k, h in template if _match_header(line, h)), None)
            if current is not None:
                sections.setdefault(current, [line])
            continue
        if current is not None and line:
            sections[current].append(line)
    return sections


def _bullets(lines: list[str]) -> list[str]:
    return [re.sub(r"^(?:[-*]|\d+[.)])\s*", "", ln) for ln in lines[1:] if re.match(r"^(?:[-*]|\d+[.)])\s", ln)]


def _prose(lines: list[str]) -> str:
    return " ".join(lines[1:]).strip()


def _parse_score(header_line: str, header: str) -> float:
    m = _match_header(header_line, header)
    raw = next((g for g in m.groups() if g), None) if m else None
    if raw is None:
        raise FormatError([f"score ilegible: {header_line!r}"])
    score = float(raw.replace(",", "."))
    if not 0 <= score <= 10:
        raise FormatError([f"score fuera de rango 0-10: {score}"])
    return score


def _parse_findings(lines: list[str], warnings: list[str], require_effort: bool) -> list[Finding]:
    findings: list[Finding] = []
    unreadable: list[str] = []
    discarded = 0
    for line in lines[1:]:
        fm = _FINDING_RE.match(line)
        if not fm or (require_effort and not fm.group("eff")):
            if _FINDING_LIKE_RE.match(line):
                unreadable.append(f"hallazgo ilegible: {line!r}")
            continue
        evidence = (fm.group("ev") or "").strip()
        if _NO_EVIDENCE_RE.match(evidence):
            warnings.append(f"{fm.group('id').upper()} descartado: sin evidencia")
            discarded += 1
            continue
        findings.append(
            Finding(
                id=fm.group("id").upper(),
                text=fm.group("text").strip(),
                impact=Level(fm.group("imp")[0].upper()),
                effort=Level(fm.group("eff")[0].upper()) if fm.group("eff") else None,
                evidence=evidence,
            )
        )
    if unreadable:
        raise FormatError(unreadable)
    if discarded and not findings:
        # El agente afirmó hallazgos pero no probó ninguno: la dimensión no puede
        # llegar al informe «limpia». Se reintenta pidiendo evidencia.
        raise FormatError([f"ningún hallazgo con evidencia ({discarded} descartados sin evidencia)"])
    return findings


def _stem(line: str) -> str:
    """Primera palabra de una línea `##` sin tildes ni signos: lo que identifica la sección."""
    words = re.findall(r"[a-z0-9]+", _fold(line[2:]))
    return words[0] if words else ""


def _unmatched_headers(text: str, template: Template) -> list[str]:
    """Líneas `##` del texto que no son ningún header exacto de la plantilla."""
    return [
        ln.strip()
        for ln in _lines(text)
        if re.match(r"^##(?!#)", ln.strip())
        and not any(_match_header(ln.strip(), h) for _, h in template)
    ]


def _require(sections: dict[str, list[str]], template: Template, text: str) -> None:
    """Falla si falta algún header; si hay una línea parecida, la cita para que el reintento sea útil."""
    unmatched = _unmatched_headers(text, template)
    problems: list[str] = []
    for key, header in template:
        if key in sections:
            continue
        near = next((ln for ln in unmatched if _stem(ln) == _stem(header)), None)
        detail = f" (hay una línea parecida que no es exacta: '{near}')" if near else ""
        problems.append(f"falta el header '{header}'{detail}")
    if problems:
        raise FormatError(problems)


def _count_finding_lines(lines: list[str]) -> int:
    return sum(1 for ln in lines[1:] if _FINDING_LIKE_RE.match(ln))


def parse_agent_output(text: str) -> DimensionResult:
    """Parsea la salida de un agente con la plantilla completa (express/full)."""
    sections = _sections(text, FULL_TEMPLATE)
    _require(sections, FULL_TEMPLATE, text)
    score = _parse_score(sections["score"][0], FULL_TEMPLATE[0][1])
    n = _count_finding_lines(sections["findings"])
    if n > MAX_FINDINGS:
        raise FormatError([f"{n} hallazgos: la plantilla permite máx {MAX_FINDINGS}"])
    warnings: list[str] = []
    findings = _parse_findings(sections["findings"], warnings, require_effort=True)
    return DimensionResult(
        score=score,
        findings=findings,
        quick_wins=_bullets(sections["quick_wins"]),
        risks=_bullets(sections["risks"]),
        missing_data=_bullets(sections["missing"]),
        warnings=warnings,
    )


def parse_ligera_output(text: str) -> LigeraResult:
    """Parsea la salida del agente único del modo ligera."""
    sections = _sections(text, LIGERA_TEMPLATE)
    _require(sections, LIGERA_TEMPLATE, text)
    score = _parse_score(sections["score"][0], LIGERA_TEMPLATE[0][1])
    n = _count_finding_lines(sections["findings"])
    if not 3 <= n <= 5:
        raise FormatError([f"{n} hallazgos: la plantilla ligera pide entre 3 y 5"])
    warnings: list[str] = []
    findings = _parse_findings(sections["findings"], warnings, require_effort=False)
    if len(findings) < 3:
        raise FormatError([f"solo {len(findings)} hallazgos con evidencia: la plantilla ligera pide 3-5"])
    resume = _bullets(sections["resume"])
    if len(resume) != 3:
        raise FormatError([f"se esperaban 3 tareas de reanudación, hay {len(resume)}"])
    return LigeraResult(
        score=score,
        state=_prose(sections["state"]),
        findings=findings,
        value=_prose(sections["value"]),
        resume_tasks=resume,
        warnings=warnings,
    )


def _fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in plain if not unicodedata.combining(c))


def dimension_from_label(text: str) -> Dimension | None:
    """Acepta el id (`producto_ux`) o la etiqueta (`Producto / UX`), sin mayúsculas ni tildes."""
    folded = _fold(text)
    for dim in Dimension:
        if folded in (dim.value, _fold(dim.label)):
            return dim
    return None


def _split_grouped(
    text: str, dims: tuple[Dimension, ...]
) -> tuple[dict[Dimension, list[str]], set[Dimension], list[str]]:
    """Trocea por separadores. Devuelve (bloques, duplicados, problemas de estructura)."""
    blocks: dict[Dimension, list[str]] = {}
    duplicated: set[Dimension] = set()
    structural: list[str] = []
    current: Dimension | None = None
    for raw in _lines(text):
        line = raw.strip()
        sep = _SEPARATOR_RE.match(line)
        if sep:
            ident = sep.group("ident")
            current = dimension_from_label(ident)
            if current is None:
                structural.append(f"dimensión desconocida en separador: {ident!r}")
                current = None
                continue
            if current not in dims:
                structural.append(f"bloque no pedido: {current.value}")
                current = None
                continue
            if current in blocks:
                duplicated.add(current)
            blocks.setdefault(current, [])
            continue
        if current is not None:
            blocks[current].append(raw)
    return blocks, duplicated, structural


def parse_grouped_partial(
    text: str, dims: tuple[Dimension, ...]
) -> tuple[dict[Dimension, DimensionResult], dict[Dimension, list[str]], list[str]]:
    """Parsea la salida de un agente de 1-2 dimensiones rescatando los bloques válidos.

    Cada bloque empieza por `# Dimensión: <id>`; con una sola dimensión el
    separador es opcional. Devuelve (resultados válidos, problemas por dimensión
    sin resultado, problemas de estructura). Un bloque duplicado es ambiguo: esa
    dimensión no se acepta. Los bloques desconocidos o no pedidos se ignoran y
    se reportan como problemas de estructura.
    """
    if len(dims) == 1 and not any(_SEPARATOR_RE.match(ln.strip()) for ln in _lines(text)):
        try:
            return {dims[0]: parse_agent_output(text)}, {}, []
        except FormatError as exc:
            return {}, {dims[0]: exc.problems}, []
    blocks, duplicated, structural = _split_grouped(text, dims)
    if not blocks and any(_H2_SEPARATOR_RE.match(ln.strip()) for ln in _lines(text)):
        structural.append(
            f"los separadores de bloque van en primer nivel: '{GROUP_SEPARATOR}<id>', no '## Dimensión:'"
        )
    results: dict[Dimension, DimensionResult] = {}
    problems: dict[Dimension, list[str]] = {}
    for dim in dims:
        if dim in duplicated:
            problems[dim] = [f"bloque duplicado para {dim.value}"]
        elif dim not in blocks:
            problems[dim] = [f"falta el bloque de {dim.value}"]
        else:
            try:
                results[dim] = parse_agent_output("\n".join(blocks[dim]))
            except FormatError as exc:
                problems[dim] = [f"{dim.value}: {p}" for p in exc.problems]
    return results, problems, structural


def parse_grouped_output(text: str, dims: tuple[Dimension, ...]) -> dict[Dimension, DimensionResult]:
    """Versión estricta: cualquier problema (incluidos bloques sobrantes) es FormatError."""
    results, problems, structural = parse_grouped_partial(text, dims)
    all_problems = structural + [p for d in dims for p in problems.get(d, [])]
    if all_problems:
        raise FormatError(all_problems)
    return results
