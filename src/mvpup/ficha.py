"""Anclaje de la pasada en la ficha del producto (Fase 5.2) vía frontmatter.

`--ficha <ruta.md>` ancla la última pasada en el frontmatter YAML de la ficha con tres
claves (`mvpup_date`, `mvpup_score`, `mvpup_report`) y NO reescribe nada más:

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
