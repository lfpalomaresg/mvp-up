"""Redacción best-effort de secretos en texto que sale de la máquina o se persiste.

Se aplica a la instantánea del repo que se envía a la API y a los mensajes de error
que acaban en consola e informes. No es una garantía: reduce el riesgo, no lo elimina.
"""

from __future__ import annotations

import re

# Patrones de claves conocidos (se redactan donde aparezcan).
_SECRET_VALUE_RE = re.compile(
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[A-Za-z0-9_-]{35}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)"
)
# Asignaciones a claves sensibles en cualquier posición: `api_key = v`, `api_key="v"`
# dentro de una llamada, `"api_key": "v"` en JSON, `SECRET_TOKEN='v'`… (se conserva el nombre).
# Credenciales dentro de URLs: esquema://usuario:CLAVE@host
_URL_CREDENTIALS_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+@")
_SECRET_ASSIGN_RE = re.compile(
    r"(?i)((?:api[_-]?key|secret|token|passw(?:or)?d|pwd|private[_-]?key|access[_-]?key)"
    r"[\w.-]*[\"']?\s*[:=]\s*)"
    # valor entrecomillado COMPLETO (espacios y comas incluidos) o valor sin comillas
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s\"',;#)}\]]{6,})"
)
REDACTED = "[REDACTADO]"


def redact(text: str) -> str:
    text = _SECRET_VALUE_RE.sub(REDACTED, text)
    def _sub(m: re.Match[str]) -> str:
        value = m.group(2)
        quote = value[0] if value[:1] in ("'", '"') else ""
        return f"{m.group(1)}{quote}{REDACTED}{quote}"

    text = _URL_CREDENTIALS_RE.sub(lambda m: f"{m.group(1)}{REDACTED}@", text)
    return _SECRET_ASSIGN_RE.sub(_sub, text)
