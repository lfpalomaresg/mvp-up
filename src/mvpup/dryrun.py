"""Modo dry-run: la pasada completa con agentes simulados y datos SINTÉTICOS.

Sirve para ver de extremo a extremo (selección por etapa, lotes, consolidación,
matriz impacto×esfuerzo, roadmap e informe) sin red, sin API key y sin coste.
Los hallazgos están inventados a propósito: cubren los cuatro cuadrantes de la
matriz, repiten un hallazgo entre dimensiones (para que aparezca como
estructural) y comparten un dato pendiente (para ver la deduplicación). Toda
evidencia va marcada `[sintético]` y el informe queda marcado como DRY-RUN:
nunca es una auditoría.
"""

from __future__ import annotations

from .dimensions import Dimension, Mode
from .orchestrator import LIGERA_TASK_KEY
from .parsing import FULL_TEMPLATE, GROUP_SEPARATOR, LIGERA_TEMPLATE
from .selection import AgentTask, Plan

SYNTHETIC = "[sintético]"

# Score por dimensión: mezcla deliberada de 🟢 / 🟡 / 🔴 para que la tabla no sea plana.
_SCORES: dict[Dimension, str] = {
    Dimension.TECNICA: "6",
    Dimension.SEGURIDAD: "4",
    Dimension.LEGAL: "3",
    Dimension.PRODUCTO_UX: "7",
    Dimension.COMERCIAL: "4,5",
    Dimension.MARKETING: "3",
    Dimension.MERCADO: "6",
    Dimension.ECONOMICA: "5",
    Dimension.OPERATIVA: "4",
    Dimension.DATOS: "2",
}

# (quick win A/B, apuesta A/M, descartar B/A, [apuesta A/A opcional]) por dimensión:
# cada uno es (hallazgo, evidencia, acción).
_FINDINGS: dict[Dimension, tuple[tuple[str, str, str], ...]] = {
    Dimension.TECNICA: (
        ("Sin tests automatizados", "no existe carpeta tests/", "Añadir pytest con un test de humo"),
        ("Dependencias sin fijar versión", "requirements.txt sin versiones", "Fijar versiones en requirements.txt"),
        ("Nombres de variables poco descriptivos", "utils.py usa x, y, tmp", "Renombrar las variables de utils.py"),
        ("Monolito sin separación de capas", "app.py concentra rutas, lógica y SQL", "Separar rutas, lógica y acceso a datos"),
    ),
    Dimension.SEGURIDAD: (
        ("Cabeceras de seguridad ausentes", "respuesta HTTP sin CSP ni HSTS", "Añadir cabeceras CSP y HSTS"),
        ("Sin límite de peticiones en el login", "ruta /login sin rate limiting", "Limitar los intentos de login por IP"),
        ("Logs demasiado verbosos en desarrollo", "config/dev.py con nivel DEBUG", "Bajar el nivel de log por defecto"),
    ),
    Dimension.LEGAL: (
        ("Falta la política de privacidad", "la web no enlaza ningún texto legal", "Publicar la política de privacidad"),
        ("Banner de cookies sin rechazo en un clic", "el banner solo ofrece aceptar", "Añadir el botón de rechazar al banner"),
        ("Licencias de iconos sin inventariar", "assets/icons sin fichero de licencia", "Inventariar las licencias de los iconos"),
    ),
    Dimension.PRODUCTO_UX: (
        ("Onboarding sin estado vacío explicado", "la pantalla inicial aparece en blanco", "Explicar el primer paso en la pantalla inicial"),
        ("Propuesta de valor poco clara en la portada", "el titular no dice qué resuelve", "Reescribir el titular de la portada"),
        ("Iconografía inconsistente entre pantallas", "dos sets de iconos distintos", "Unificar el set de iconos"),
    ),
    Dimension.COMERCIAL: (
        ("Oferta sin garantía formulada", "la página de precios no menciona garantía", "Formular una garantía en la página de precios"),
        ("Pricing sin justificar frente a la competencia", "un único plan sin comparativa", "Justificar el precio frente a la competencia"),
        ("Material de venta en formatos dispares", "carpeta ventas/ con pdf, ppt y docx", "Unificar el material de venta en un formato"),
        ("Rediseñar el proceso de venta de principio a fin", "no hay embudo documentado", "Documentar el embudo de venta de extremo a extremo"),
    ),
    Dimension.MARKETING: (
        ("Sin prueba social visible", "ningún testimonio ni caso en la web", "Publicar un testimonio en la portada"),
        ("Propuesta de valor poco clara en la portada", "el titular es genérico", "Reescribir el titular de la portada"),
        ("Colores de marca no definidos", "cada pieza usa un azul distinto", "Definir la paleta de marca"),
    ),
    Dimension.MERCADO: (
        ("Competidores directos sin tabla comparativa", "docs/ no recoge competencia", "Montar la tabla comparativa de competidores"),
        ("Pricing sin justificar frente a la competencia", "sin referencia de precios del sector", "Justificar el precio frente a la competencia"),
        ("Tendencias del sector sin fuente citada", "la ficha cita cifras sin enlace", "Citar la fuente de cada cifra del sector"),
    ),
    Dimension.ECONOMICA: (
        ("Costes recurrentes sin inventariar", "ningún fichero lista hosting ni APIs", "Inventariar hosting, APIs y licencias"),
        ("Margen unitario sin calcular", "no hay hoja de costes por cliente", "Calcular el margen por cliente"),
        ("Gasto hundido documentado solo de memoria", "sin registro de horas invertidas", "Registrar las horas invertidas"),
        ("Rehacer el modelo económico completo", "no existe modelo de ingresos", "Construir el modelo de ingresos"),
    ),
    Dimension.OPERATIVA: (
        ("Onboarding de cliente sin checklist", "los pasos viven en la cabeza del operador", "Escribir la checklist de alta de cliente"),
        ("Soporte sin canal definido", "los clientes escriben a un correo personal", "Abrir un canal único de soporte"),
        ("Plantillas de correo sin unificar", "tres versiones del mismo correo", "Unificar las plantillas de correo"),
    ),
    Dimension.DATOS: (
        ("Sin analítica instalada", "index.html sin ningún script de medición", "Instalar una analítica web"),
        ("Sin canal de feedback de usuarios", "no hay formulario ni correo de feedback", "Añadir un formulario de feedback"),
        ("Dashboard decorativo sin métrica accionable", "panel con gráficas que nadie consulta", "Elegir una métrica accionable para el panel"),
    ),
}
# Hallazgo compartido por TODAS las dimensiones: aparece como estructural en cualquier plan.
_SHARED_FINDING = (
    "Sin métricas de uso para decidir",
    "ninguna decisión del último mes se tomó con datos",
    "Definir las tres métricas de uso que guían las decisiones",
)
_SHARED_MISSING = "Volumen mensual de usuarios activos"
_LEVELS = ("A · Esfuerzo: B", "A · Esfuerzo: M", "M · Esfuerzo: B", "B · Esfuerzo: A", "A · Esfuerzo: A")


def _finding_lines(dim: Dimension) -> list[str]:
    own = list(_FINDINGS[dim])
    rows = [own[0], own[1], _SHARED_FINDING, own[2], *own[3:]]
    return [
        f"- [H{n}] {text} · Impacto: {_LEVELS[n - 1]} · Evidencia: {SYNTHETIC} {evidence} · Acción: {action}"
        for n, (text, evidence, action) in enumerate(rows, 1)
    ]


def synthetic_dimension_output(dim: Dimension) -> str:
    """Salida sintética válida con la plantilla completa (express/full)."""
    h = dict(FULL_TEMPLATE)
    lines = [
        h["score"].replace("X/10", f"{_SCORES[dim]}/10"),
        h["findings"],
        *_finding_lines(dim),
        h["quick_wins"],
        f"- {_FINDINGS[dim][0][0]}: resolverlo esta semana",
        h["risks"],
        f"- {dim.label}: el hueco crece con cada cliente nuevo",
        h["missing"],
        f"- {_SHARED_MISSING}",
        f"- Dato específico de {dim.label.lower()} que solo tiene el operador",
    ]
    return "\n".join(lines) + "\n"


def synthetic_ligera_output() -> str:
    """Salida sintética válida con la plantilla ligera (un agente)."""
    h = dict(LIGERA_TEMPLATE)
    lines = [
        h["score"].replace("X/10", "4/10"),
        h["state"],
        "Prototipo sintético: README y una pantalla; nada desplegado todavía.",
        h["findings"],
        f"- [H1] Sin despliegue · Impacto: A · Evidencia: {SYNTHETIC} README sin URL",
        f"- [H2] Ficha desalineada con el repo · Impacto: M · Evidencia: {SYNTHETIC} git log sin actividad",
        f"- [H3] {_SHARED_FINDING[0]} · Impacto: M · Evidencia: {SYNTHETIC} {_SHARED_FINDING[1]}",
        h["value"],
        "Sirve al objetivo de reducir trabajo manual; conviene retomarla, no archivarla.",
        h["resume"],
        "1. Desplegar el prototipo en una URL pública",
        "2. Actualizar la ficha con el estado real del repo",
        "3. Definir la métrica que decide si sigue viva",
    ]
    return "\n".join(lines) + "\n"


def synthetic_task_output(task: AgentTask) -> str:
    """Salida de un agente: un bloque por dimensión, con separador si cubre dos."""
    if len(task.dimensions) == 1:
        return synthetic_dimension_output(task.dimensions[0])
    return "\n".join(
        f"{GROUP_SEPARATOR}{d.value}\n{synthetic_dimension_output(d)}" for d in task.dimensions
    )


def dry_run_responses(plan: Plan, mode: Mode) -> dict[str, str]:
    """Respuestas `{task_key: salida}` para construir un `FakeRunner` del plan dado."""
    if mode is Mode.LIGERA:
        return {LIGERA_TASK_KEY: synthetic_ligera_output()}
    return {task.key: synthetic_task_output(task) for task in plan.tasks}
