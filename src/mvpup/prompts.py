"""Constructor de prompts de los agentes (fuente: skill/references/dimensiones.md).

Los bloques de dimensión están embebidos LITERALES para que el paquete funcione
instalado; `tests/test_prompts.py` comprueba que no divergen del markdown.
"""

from __future__ import annotations

from .dimensions import Dimension, Mode
from .intake import Intake
from .parsing import FULL_TEMPLATE, GROUP_SEPARATOR, LIGERA_TEMPLATE
from .selection import AgentTask

D = Dimension

# Copia LITERAL de cada bloque `## N · ...` de dimensiones.md (lo vigila un test de deriva).
DIMENSION_BLOCKS: dict[Dimension, str] = {
    D.TECNICA: '- **Evalúa:** calidad y estructura del código, arquitectura front/back, deuda técnica, tests, dependencias desactualizadas/vulnerables, capacidad de crecer (¿aguanta 10× usuarios/clientes?), documentación técnica, facilidad de traspaso a otro desarrollador.\n- **Fuentes:** repo local (leerlo), `package.json`/lockfiles, estructura de carpetas, README, CI si existe. Si es web: criterios de `tool-quality-gate`.\n- **N/A si:** el producto no tiene software.',
    D.SEGURIDAD: '- **Evalúa:** credenciales expuestas, endpoints sin proteger, auth/authz, validación de inputs, rate limiting, headers, RLS/permisos de BBDD, gestión de secretos, dependencias con CVEs.\n- **Fuentes:** repo + URL desplegada. Criterios de `tool-seguridad-ia` (10 riesgos críticos) y rama seguridad de `tool-site-audit`.\n- **N/A si:** no hay software ni datos de clientes. Si hay datos de clientes aunque no haya app (p.ej. hojas de cálculo de un servicio), evaluar la variante "servicio": dónde viven los datos, quién accede, copias.',
    D.LEGAL: '- **Evalúa:** RGPD (base jurídica, política privacidad, encargados de tratamiento), LSSI-CE/aviso legal, cookies (criterio AEPD), términos de servicio, propiedad intelectual y marca (¿registrada? ¿OEPM?), contratos con clientes/proveedores, licencias de dependencias y assets.\n- **Fuentes:** URL desplegada (textos legales), repo (licencias), contexto de negocio. Rama legal de `tool-site-audit`.\n- **Variante servicio:** contratos, hojas de encargo, seguros de responsabilidad, normativa sectorial aplicable.',
    D.PRODUCTO_UX: '- **Evalúa:** claridad de la propuesta de valor en 5 segundos, fricción del onboarding, flujo principal (¿cuántos pasos hasta el valor?), estados vacíos/de error, accesibilidad básica, móvil, coherencia visual, ¿qué le sobra? (feature creep).\n- **Fuentes:** usar el producto de verdad (URL o app local), capturas, README de usuario.',
    D.COMERCIAL: '- **Evalúa:** oferta formulada (¿Grand Slam Offer estilo Hormozi?: resultado soñado × probabilidad ÷ tiempo × esfuerzo), pricing definido y justificado, garantías, objeciones mapeadas, canales de venta activos, proceso de venta repetible, ¿quién vende si no vende el operador?\n- **Fuentes:** web/materiales de venta, ficha AI_OS del producto, ejercicio Capa 3 si existe (`project_blindbeds_capa3_oferta`).',
    D.MARKETING: '- **Evalúa:** posicionamiento diferenciado (¿por qué tú y no el de al lado?), ICP definido, presencia y contenido (¿hay motor de contenido o silencio?), prueba social (testimonios, casos), narrativa/hype honesto (demo grabable, historia contable), SEO básico.\n- **Fuentes:** web, LinkedIn/redes del producto, outputs de `marketing-positioning`/`marketing-icp` si existen (leerlos, no relanzar).',
    D.MERCADO: '- **Evalúa:** tamaño y accesibilidad del nicho, 3-5 competidores directos con precios, hueco real, tendencias del sector, riesgo de plataforma o regulatorio, oportunidades adyacentes (¿a quién más le sirve esto sin reconstruirlo?).\n- **Fuentes:** búsqueda web (patrón de `strategy-research` modo quick: 3-5 fuentes citadas). Este agente SÍ navega.',
    D.ECONOMICA: '- **Evalúa:** coste de desarrollo hundido (informativo), costes recurrentes (hosting, APIs, dominios, licencias — buscarlos de verdad en el repo/config), coste por cliente adicional, precio vs coste (margen unitario), break-even (¿cuántos clientes cubren los fijos?), ingresos actuales si los hay.\n- **Regla dura:** NO inventar cifras. Todo importe sin fuente = N/D + pedir el dato.\n- **Fuentes:** configs del repo (qué servicios usa), ficha AI_OS, datos que aporte el operador.',
    D.OPERATIVA: '- **Evalúa:** qué pasos dependen manualmente del operador (mapa honesto), ¿qué pasa si el operador desaparece 2 semanas?, onboarding de un cliente nuevo (pasos, horas), soporte (¿canal definido?), procesos documentados vs en la cabeza, automatizable con loops (`automation-loop-engine`).\n- **Fuentes:** ficha AI_OS, workflows documentados, entrevista corta al operador si hace falta.',
    D.DATOS: '- **Evalúa:** ¿hay analítica instalada? (web/producto), ¿se miden las 3-5 métricas que importan para el objetivo de valor?, ¿hay canal de feedback de usuarios?, ¿las decisiones del último mes se tomaron con datos o a ojo?, ¿qué dato barato de instalar cambiaría la próxima decisión?\n- **Nota:** esta dimensión alimenta a todas las demás en la re-auditoría — sin medición, los Δ de score son opinión.\n- **Fuentes:** repo (¿hay tracking?), herramientas conectadas, ficha AI_OS.',
}

RUBRIC = (
    "Rúbrica 0-10: 0-2 crítico o inexistente · 3-4 deficiente, bloquea el escalado · "
    "5-6 funcional con huecos claros · 7-8 sólido, mejoras incrementales · 9-10 listo para escalar."
)

_FORMAT_BODY = """\
{score}
{findings}
- [H1] <hallazgo> · Impacto: A/M/B · Esfuerzo: A/M/B · Evidencia: <archivo/dato concreto>
{quick_wins}
{risks}
{missing}"""


def _format_block() -> str:
    headers = dict(FULL_TEMPLATE)
    return _FORMAT_BODY.format(**{k: headers[k] for k in ("score", "findings", "quick_wins", "risks", "missing")})


def _header(intake: Intake, role: str) -> str:
    return (
        f"Eres {role} de una auditoría MVP-UP.\n"
        f"Producto: {intake.product} · Etapa: {intake.stage.value} · "
        f"Objetivo de valor: {intake.objective.value}\n"
        f"Ruta local: {intake.repo_path or 'N/D'} · URL desplegada: {intake.url or 'no desplegado'}\n"
        f"Contexto de negocio: {intake.context.strip() or 'N/D'}\n\n"
        "REGLAS: Solo análisis. NO modifiques archivos, NO hagas commits, NO llames APIs de pago.\n"
        "Evalúa únicamente lo verificable; lo que no puedas verificar, márcalo como N/D.\n"
        "Todo hallazgo debe citar su evidencia (archivo, URL o dato); sin evidencia no se incluye.\n"
    )


def _dimension_section(dim: Dimension, intake: Intake) -> str:
    text = f"### {dim.label}\n{DIMENSION_BLOCKS[dim]}"
    if not intake.has_software:
        text += (
            "\n- **Producto sin software:** aplica la variante servicio de este bloque si la tiene."
        )
    return text


def build_task_prompt(task: AgentTask, intake: Intake) -> str:
    """Prompt para un agente de 1 dimensión o de 2 agrupadas (express)."""
    if intake.mode is Mode.LIGERA:
        return build_ligera_prompt(intake)
    dims = task.dimensions
    if not 1 <= len(dims) <= 2:
        raise ValueError("un agente cubre 1 o 2 dimensiones (nunca más de 2)")
    labels = " + ".join(d.label for d in dims)
    parts = [_header(intake, f"el agente de la dimensión [{labels}]")]
    parts.append("Evalúa lo que indica tu bloque de dimensión:\n")
    parts.extend(_dimension_section(d, intake) for d in dims)
    fmt = _format_block()
    if len(dims) == 1:
        parts.append(f"\nDevuelve EXACTAMENTE este formato (headers ## literales):\n\n{fmt}")
    else:
        parts.append(
            "\nCubres DOS dimensiones. Devuelve un bloque por dimensión, cada uno precedido de "
            "su línea separadora literal, y dentro de cada bloque EXACTAMENTE este formato:\n"
        )
        for d in dims:
            parts.append(f"{GROUP_SEPARATOR}{d.value}\n{fmt}\n")
    parts.append(f"\n{RUBRIC}")
    return "\n".join(parts)


def build_ligera_prompt(intake: Intake) -> str:
    headers = dict(LIGERA_TEMPLATE)
    return (
        _header(intake, "el agente único de una pasada LIGERA (diagnóstico de semilla, no auditoría completa)")
        + f"Lee primero su ficha ({intake.ficha_path or 'N/D: no hay ficha, audita solo el repo'}) "
        f"y después el repo {intake.repo_path or 'N/D'} (README, docs, estructura, "
        "git log --oneline -10).\n"
        f"Contexto del operador: {intake.wip_context.strip() or 'N/D'}\n"
        "Nada se modifica, instala ni arranca. Máx ~40 líneas.\n\n"
        "Devuelve EXACTAMENTE (headers ## literales):\n\n"
        f"{headers['score']}\n"
        f"{headers['state']}\n"
        f"{headers['findings']}\n"
        "- [H1] <hallazgo> · Impacto: A/M/B · Evidencia: <archivo/dato concreto>\n"
        f"{headers['value']}\n"
        f"{headers['resume']}\n"
        "1. <tarea>\n2. <tarea>\n3. <tarea>\n"
    )
