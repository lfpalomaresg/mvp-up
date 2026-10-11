"""Anclaje de la pasada en la ficha del producto (Fase 5.2).

Dos anclajes, los dos sin reescribir nada ajeno:

1. `anchor_frontmatter` (siempre con `--ficha`): tres claves en el frontmatter YAML
   (`mvpup_date`, `mvpup_score`, `mvpup_report`).
2. `anchor_ficha` (opt-in con `--anclar`): el bloque visible «⚡ MVP-UP X/10 — LEER AL
   RETOMAR» al final de la ficha, idempotente por informe.

Reglas del frontmatter:

- el cuerpo de la ficha se conserva byte a byte (saltos de línea CRLF/LF y BOM incluidos);
- las demás claves del frontmatter se conservan tal cual (orden, espacios, comentarios);
- las claves `mvpup_*` se sustituyen en su sitio si ya existen o se añaden al final del
  bloque; una segunda pasada con el mismo informe no cambia nada (idempotente);
- si la ficha no existe se crea una mínima.

Se edita línea a línea sin parser YAML (el núcleo no tiene dependencias): por eso las
claves son planas y el valor de la ruta va entre comillas dobles escapadas.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .scoring import fmt_score

FRONTMATTER_KEYS = ("mvpup_date", "mvpup_score", "mvpup_report")
_KEY_RE = re.compile(r"^(" + "|".join(FRONTMATTER_KEYS) + r")\s*:")
_FENCES = ("---", "...")
_BOM = "﻿"


def _yaml_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def anchor_values(when: date, score: float | None, report_path: Path | str) -> dict[str, str]:
    return {
        "mvpup_date": when.isoformat(),
        "mvpup_score": "null" if score is None else f"{float(score):.1f}",
        "mvpup_report": _yaml_string(str(report_path)),
    }


def _split(text: str) -> tuple[str, str, list[str] | None, str]:
    """(BOM, salto de línea, líneas del frontmatter o None, cuerpo intacto)."""
    bom = _BOM if text.startswith(_BOM) else ""
    rest = text[len(bom):]
    newline = "\r\n" if "\r\n" in rest else "\n"
    lines = rest.split(newline)
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] in _FENCES:
                head = sum(len(ln) + len(newline) for ln in lines[: i + 1])
                return bom, newline, lines[1:i], rest[head:]
    return bom, newline, None, rest  # sin frontmatter (o fence inicial sin cerrar: es cuerpo)


def _merge(existing: list[str], values: dict[str, str]) -> list[str]:
    """Sustituye las claves mvpup_* en su sitio (sin duplicar) y añade las que falten al final."""
    merged: list[str] = []
    seen: set[str] = set()
    for line in existing:
        m = _KEY_RE.match(line)
        if not m:
            merged.append(line)
            continue
        key = m.group(1)
        if key not in seen:
            merged.append(f"{key}: {values[key]}")
            seen.add(key)
    merged.extend(f"{key}: {values[key]}" for key in FRONTMATTER_KEYS if key not in seen)
    return merged


def anchor_frontmatter(
    ficha: Path,
    when: date,
    score: float | None,
    report_path: Path | str,
    product: str | None = None,
) -> bool:
    """Ancla la pasada en el frontmatter de `ficha`. Devuelve True si escribió algo."""
    values = anchor_values(when, score, report_path)
    if ficha.exists():
        original = ficha.read_bytes().decode("utf-8")
        bom, newline, existing, body = _split(original)
    else:
        name = product or ficha.stem
        bom, newline, existing = "", "\n", []
        body = f"\n# {name}\n\n- Qué es: N/D (completar)\n- Estado: auditado con MVP-UP\n"
    block = newline.join(["---", *_merge(existing or [], values), "---"]) + newline
    updated = bom + block + body
    if ficha.exists() and updated == original:
        return False
    ficha.parent.mkdir(parents=True, exist_ok=True)
    ficha.write_bytes(updated.encode("utf-8"))
    return True


def read_frontmatter(ficha: Path) -> dict[str, str]:
    """Valores CRUDOS (texto YAML sin interpretar) de las claves mvpup_* de la ficha."""
    _, _, existing, _ = _split(ficha.read_bytes().decode("utf-8"))
    out: dict[str, str] = {}
    for line in existing or []:
        m = _KEY_RE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = line[m.end():].strip()
    return out


ANCHOR_TITLE = "## ⚡ MVP-UP {score}/10 ({date}) — LEER AL RETOMAR"


def anchor_ficha(
    ficha: Path,
    report_path: Path,
    score: float | None,
    when: date,
    product: str | None = None,
    repo: str | None = None,
) -> bool:
    """Añade el bloque «salta al retomar» al final de la ficha (idempotente por informe).

    Si la ficha no existe se crea la mínima (qué es / estado / repo / informe). Devuelve True
    si escribió algo. Nunca reescribe contenido existente: solo añade al final, con el mismo
    salto de línea que ya usa la ficha (CRLF o LF).
    """
    title = ANCHOR_TITLE.format(score=fmt_score(score, 1), date=when.isoformat())
    pointer = f"Informe: `{report_path}`"
    block_lines = ["", title, f"{pointer} — la próxima sesión sobre este producto arranca leyéndolo."]
    if ficha.exists():
        text = ficha.read_bytes().decode("utf-8")
        if pointer in text:  # idempotente por INFORME, no por fecha/score
            return False
        newline = "\r\n" if "\r\n" in text else "\n"
        body = text.rstrip("\r\n") + newline if text.strip() else ""
        ficha.write_bytes((body + newline.join(block_lines) + newline).encode("utf-8"))
        return True
    ficha.parent.mkdir(parents=True, exist_ok=True)
    name = product or ficha.stem
    head = [f"# {name}", "", "- Qué es: N/D (completar)", "- Estado: auditado con MVP-UP",
            f"- Repo: `{repo or 'N/D'}`", f"- Informe: `{report_path}`"]
    ficha.write_text("\n".join(head + block_lines) + "\n", encoding="utf-8")
    return True
