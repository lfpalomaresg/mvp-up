# Bitácora de automejora — MVP-UP (código)

Cada loop: audit → ítem de mayor impacto → test en ROJO → implementación → VERDE →
revisión adversarial (careo) → sello conclave → commit.

## Loop 0 — Módulo base (2026-10-04)
- **Hecho:** `dimensions`, `intake`, `selection`, `parsing`, `scoring` + 49 tests.
- **Careo:** Codex ×4 rondas (5+4+2 hallazgos IMPORTANTES corregidos; la 4ª se contradijo con
  la 3ª sobre normalizar espacios en headers → oscilación, se corta). Desempate Gemini: APTO
  + 2 MENOR aplicados (`###` no corta sección; dimensión inválida → `IntakeError`).
- **Decisiones:** headers estrictamente exactos (completos o sin su paréntesis final);
  >7 hallazgos = formato inválido (reintento) en vez de truncar; add/remove del operador que
  saca express de 3-5 agentes = aviso, no bloqueo (la skill le da esa potestad).

## Loop 1 — Constructor de prompts
- **Audit (vs spec):** [CRÍTICO] no hay prompts/runners/consolidación → no se puede ejecutar
  una pasada · [CRÍTICO] sin informe/matriz/roadmap · [IMPORTANTE] agentes agrupados sin
  parseo · comparación Δ · CLI · runner real con política de modelos · [MENOR] slug seguro de
  ruta, síntesis de cartera, hallazgos estructurales.
- **Hecho:** `prompts.py` (plantilla común + bloque de dimensión + variante servicio +
  prompt agrupado con separador `# Dimensión: <id>` + prompt ligera).
- **Careo r1 (Codex NO_APTO):** [CRÍTICO] el prompt agrupado pedía 2 bloques que el parser
  fusionaba → nuevo `parse_grouped_output` (un resultado por dimensión, valida
  duplicados/ausentes/no pedidos) · bloques ahora copia LITERAL del markdown · ligera recibe
  ficha y contexto WIP. [MENOR] aceptado sin cambio: el `- [H1]` en la misma línea que el
  header en dimensiones.md es compresión del markdown, no formato canónico.
- **Test clave:** los bloques no divergen de `skill/references/dimensiones.md`
  (drift test) y la plantilla que se pide es la misma que el validador acepta.
