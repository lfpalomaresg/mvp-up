"""Configuración: `.env` (gitignoreado) + política de modelos.

Secretos: la API key solo se lee del entorno o de `.env`; nunca se escribe,
nunca se registra y nunca aparece en mensajes de error.

Política de modelos (skill/SKILL.md, «Política de modelos»): los agentes de
dimensión usan tier medio (Sonnet). Prohibidos: tier ligero (Haiku) — evaluar
impacto/esfuerzo requiere juicio — y Fable/Mythos — restricción del operador.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_AGENT_MODEL = "claude-sonnet-5-5"
AGENT_MODEL_ENV = "MVPUP_AGENT_MODEL"
API_KEY_ENV = "ANTHROPIC_API_KEY"

_FORBIDDEN = ("fable", "mythos", "haiku")


class ModelPolicyError(ValueError):
    pass


def check_model(model: str) -> str:
    name = model.strip()
    if not re.fullmatch(r"claude-[a-z0-9.-]+", name):
        raise ModelPolicyError(f"identificador de modelo no válido: {name!r}")
    banned = next((b for b in _FORBIDDEN if b in name), None)
    if banned:
        raise ModelPolicyError(
            f"modelo {name!r} prohibido por la política de MVP-UP ({banned}): "
            f"usa el tier medio, p.ej. {DEFAULT_AGENT_MODEL}"
        )
    return name


def load_dotenv(path: Path | str = ".env", override: bool = False) -> list[str]:
    """Carga KEY=VALUE de un `.env` sin dependencias. Devuelve las CLAVES cargadas.

    No sobrescribe variables ya definidas (salvo `override`). Ignora comentarios
    y líneas mal formadas. Nunca devuelve ni imprime valores.
    """
    p = Path(path)
    if not p.is_file():
        return []
    loaded: list[str] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def agent_model() -> str:
    return check_model(os.environ.get(AGENT_MODEL_ENV) or DEFAULT_AGENT_MODEL)
