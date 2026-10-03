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

## Loop 2 — Orquestador de la Fase 1
- **Audit:** con prompts y parser listos, el hueco CRÍTICO es que nada ejecuta la pasada.
- **Hecho:** `runners.py` (protocolo `AgentRunner` + `FakeRunner` determinista) y
  `orchestrator.py` (`run_pass`: lotes ≤5 en paralelo, un reintento con prompt reforzado ante
  formato inválido o excepción, "sin evaluar" al segundo fallo, la pasada nunca se bloquea).
- **Test clave:** pico de concurrencia medido con barrera = 5 en modo full (10 agentes).
- **Careo r1 (Codex NO_APTO, 2 IMPORTANTES):** un agente agrupado perdía el bloque válido si
  el otro fallaba → `parse_grouped_partial` + `_run_task` acumula bloques válidos entre
  intentos · sin timeout un agente colgado bloqueaba la pasada → timeout por intento
  (`agent_timeout`, 900 s por defecto) con hilo daemon; el hilo colgado sigue vivo pero la
  pasada continúa (limitación documentada: puede superar 5 hilos vivos momentáneamente).
- **Careo r2 (Codex NO_APTO):** los hilos colgados podían acumular >5 llamadas vivas →
  `BoundedSemaphore(5)` liberado al terminar el hilo real; esperar hueco también tiene timeout.
  Bloques sobrantes en agentes agrupados: decisión → se registran en el log, NO se reintenta
  (las dimensiones pedidas ya son válidas; reintentar cuesta sin aportar información).

## Loop 3 — Consolidación (Fase 2)
- **Audit:** la pasada ya produce resultados por dimensión, pero no hay matriz ni detección
  de hallazgos estructurales: el valor de la skill (orden de ataque) aún no existe.
- **Hecho:** `consolidation.py`: `build_matrix` (4 cuadrantes de la plantilla, TODOS los
  hallazgos, orden por impacto → peso del objetivo → esfuerzo) y `structural_findings`
  (heurística léxica determinista entre dimensiones distintas, máx 3; es candidato, no juicio).
- **Careo r1 (Codex NO_APTO):** sinónimos de un solo término («Sin analítica» / «No hay
  analítica») no se agrupaban → singletons idénticos cuentan como relacionados (pero 1 término
  compartido con palabras extra no) · orden dependiente de qué agente terminó antes → orden
  canónico total (impacto, dimensión, id, texto) antes de agrupar y dentro de cada grupo.
