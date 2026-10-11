"""Runners: quién ejecuta el prompt de un agente.

El orquestador solo conoce el protocolo `AgentRunner`. `FakeRunner` sirve para
tests, dry-run y demos sin red; los runners reales viven en módulos aparte.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, Union

Response = Union[str, Callable[[str], str]]


class AgentRunner(Protocol):
    def run(self, prompt: str, *, task_key: str) -> str: ...


def _as_sequence(key: str, value: object) -> tuple[Response, ...]:
    """Normaliza una respuesta (texto, callable o secuencia de ambos) y rechaza lo demás."""
    items: tuple[object, ...] = tuple(value) if isinstance(value, (list, tuple)) else (value,)
    checked: list[Response] = []
    for item in items:
        if isinstance(item, str) or callable(item):
            checked.append(item)
    if not checked or len(checked) != len(items):
        raise TypeError(
            f"respuesta de {key!r} no válida: debe ser texto, un callable prompt->str "
            f"o una secuencia no vacía de ellos (recibido {type(value).__name__})"
        )
    return tuple(checked)


class FakeRunner:
    """Devuelve respuestas predefinidas por `task_key` (o `"*"` como comodín).

    Cada valor puede ser una respuesta o una secuencia de respuestas que se
    consumen en orden (la última se repite). Una respuesta puede ser un string
    o un callable `prompt -> str` (que puede lanzar excepciones). Cualquier otra
    cosa se rechaza al construir el runner, no al ejecutar.
    """

    def __init__(self, responses: Mapping[str, Response | Sequence[Response]]):
        self._responses: dict[str, tuple[Response, ...]] = {
            key: _as_sequence(key, value) for key, value in responses.items()
        }
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    def run(self, prompt: str, *, task_key: str) -> str:
        key = task_key if task_key in self._responses else "*"
        if key not in self._responses:
            raise KeyError(f"FakeRunner sin respuesta para {task_key!r}")
        with self._lock:
            self.calls.append((task_key, prompt))
            n = self._counts.get(task_key, 0)
            self._counts[task_key] = n + 1
        sequence = self._responses[key]
        value = sequence[min(n, len(sequence) - 1)]
        return value(prompt) if callable(value) else value
