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

## Loop 4 — Roadmap H1/H2/H3 + TOP-5 (Fase 3)
- **Audit:** la matriz existe pero no se traduce en acciones ni en el TOP-5 que el operador
  autoriza — el entregable principal de la skill.
- **Hecho:** `roadmap.py`: H1 = quick wins · H2 = apuestas de esfuerzo medio + «si sobra
  tiempo» · H3 = apuestas de esfuerzo alto SOLO si su dimensión pesa ×2 en el objetivo (si
  no, «no justificadas») · «descartar» nunca entra · coste N/D y ejecutor «por decidir»
  (no se inventan) · fuera de carriles WIP todo queda «encolar» · TOP-5: estructurales
  primero, sin duplicar sus hallazgos.
- **Careo r1 (Codex NO_APTO, 4 IMPORTANTES, todos aplicados):** TOP-5 solo con hallazgos
  PROGRAMADOS (un estructural «descartar» ya no se cuela) · «si sobra tiempo» de impacto BAJO
  → backlog, no H2 · `costs` con fuente por (dimensión, hallazgo), el resto N/D · TOP-5 marca
  «encolar» fuera de carriles WIP.
- **Careo r2 (Codex NO_APTO, 1 IMPORTANTE):** las dimensiones de un estructural en el TOP-5
  salían también de entradas no programadas → ahora solo cuentan las programadas, y con <2
  dimensiones deja de ser estructural.

## Loop 5 — Informe versionado + comparación (Fases 4-5)
- **Audit:** hay roadmap pero no entregable: ni informe, ni versionado, ni Δ entre pasadas
  — sin esto MVP-UP es «una foto», justo lo que la skill dice no ser.
- **Hecho:** `report.py` (MD con TODOS los headers de `plantilla-informe.md` en orden —
  test lo comprueba contra la plantilla—, JSON gemelo, numeración de pasadas, nunca
  sobrescribe, slug a prueba de `../`, informe ligera con sus headers, datos pendientes
  deduplicados) y `compare.py` (Δ por dimensión, caída en 🔴 con causa probable, cambio de
  objetivo → «no comparables directamente» + recálculo con pesos nuevos, cambio de etapa,
  aviso >6 meses, acciones del roadmap anterior que ya no aparecen = candidatas a hechas
  «a confirmar por el operador», JSON anterior corrupto → aviso, no excepción).
- **Dogfooding:** ejecución extremo a extremo con `FakeRunner` → detectados datos pendientes
  duplicados (corregido) y acciones estructurales repetidas por dimensión en el roadmap
  (→ candidato a loop posterior).
- **Careo r1 (Codex NO_APTO, 3 IMPORTANTES + 1 MENOR, todos aplicados):** una pasada solo en
  `.md` (canónico) ahora cuenta y avisa «sin JSON gemelo» · con cambio de objetivo la tabla
  muestra `n/c (8→6)` en vez de Δ con 🔴 · la causa de una caída ya no se inventa: solo
  hallazgos de impacto alto NUEVOS respecto a la pasada anterior (el JSON guarda ahora los
  hallazgos) y siempre con su evidencia · «6 meses» = meses naturales, no 183 días.
- **Careo r2 (Codex NO_APTO, 2 IMPORTANTES):** con objetivo cambiado la Evolución ya no
  narra caídas en 🔴 ni causas (lista variaciones «sin valorar») · solo los `.md` cuentan
  como pasada; un `.json` huérfano se ignora.
- **Careo r3 (Codex NO_APTO, 1 IMPORTANTE):** `*-informe*.md` aceptaba borradores/backups
  como pasadas → `REPORT_NAME_RE` exige `YYYY-MM-DD-informe[-N]` (compartido con cartera).
  Ronda 4 = solo verificación de este arreglo.

## Loop 6 — Runner real con la API de Claude + configuración
- **Audit:** todo funciona con `FakeRunner`, pero no hay forma de lanzar agentes reales: la
  herramienta aún no audita nada de verdad.
- **Hecho:** `config.py` (`.env` sin dependencias que nunca devuelve valores; política de
  modelos: Sonnet 5.5 por defecto, Fable/Mythos/Haiku prohibidos, identificador validado) y
  `anthropic_runner.py` (`messages.create` con `system` de solo análisis, effort `medium`,
  `refusal`/`max_tokens` → error que el orquestador reintenta; instantánea del repo).
  No se activa el `fallbacks` server-side: su destino no se controla y podría enrutar a un
  modelo vetado por el operador.
- **Careo (Codex, 3 rondas + verificación, 2 CRÍTICOS en r1):** symlinks a `.env`, carpetas
  `credentials/`, claves dentro de ficheros normales, `</repo_snapshot>` inyectado, SDK
  <1.11, ficheros sin trackear ignorados → defensa en capas: exclusión por nombre en toda la
  ruta, nunca symlinks (ni la raíz), redacción de patrones de claves y de asignaciones en
  cualquier posición (valores entrecomillados completos) sobre TODA la instantánea (árbol y
  git log incluidos), reglas en `system` y la instantánea en bloque aparte. Documentado como
  best-effort, no garantía.

## Loop 7 — Síntesis de cartera (Fase 2, punto 5)
- **Audit:** SKILL.md exige, con 2+ proyectos, patrones transversales que ningún informe
  individual muestra; no existía.
- **Hecho:** `portfolio.py`: último informe VÁLIDO por producto (esquema estricto, nombre
  exacto, retrocede si el último está corrupto), ranking por score global DENTRO de cada
  objetivo de valor, tabla de cobertura por dimensión, patrones: dimensión débil en toda la
  cartera (solo con mayoría evaluada; si no, «débil donde se evaluó»), Datos y medición sin
  medir (línea propia) y resto sin medir agrupado, dominancias sistemáticas «A > B en n/n».
- **Careo (Codex, 3 rondas + verificación):** cobertura engañosa, ausentes no contados,
  ranking mezclando objetivos, esquema laxo (`schema: true` colaba), score 0 tratado como
  ausente → todo corregido con test en rojo previo.

## Loop 8 — Fusión de acciones estructurales en el roadmap (hallazgo de dogfooding)
- **Audit:** la ejecución extremo a extremo del loop 5 mostró la misma acción repetida
  una vez por dimensión cuando un hallazgo es estructural: ruido justo en el entregable.
- **Hecho:** `build_roadmap(..., structural=...)` fusiona las entradas PROGRAMADAS de un
  estructural (2+ dimensiones) en una acción en su horizonte más temprano que «sube A + B»;
  lo descartado/backlog/no justificado nunca se fusiona. `top_five` pone primero las
  fusionadas. JSON con lista de dimensiones por acción.
- **Careo (Codex, 2 rondas):** la fusión perdía los costes de las entradas relacionadas →
  coste combinado por dimensión (nunca sumado ni inventado; N/D si ninguno).

## Loop 9 — CLI (`mvpup plan · run · validate · cartera`)
- **Audit:** el orquestador solo era usable como librería; sin punto de entrada no hay
  forma práctica de lanzar una pasada, validar salidas de subagentes ni ver la cartera.
- **Hecho:** `cli.py` + `python -m mvpup` + entry point `mvpup`: `plan` (sin red: selección,
  lotes, avisos, coste orientativo de SKILL.md, `--show-prompts`), `run` (fake/anthropic,
  informe versionado, TOP-5 pendiente de autorización), `validate` (plantilla completa,
  agrupada o ligera) y `cartera`. README con uso y códigos de salida.
- **Careo r1 (Codex NO_APTO, 1 CRÍTICO + 4 IMPORTANTES):** el texto de excepciones del SDK
  podía llevar credenciales a consola/JSON → `redaction.py` compartido (+ credenciales en
  URLs) aplicado al log · sin API key la pasada «tenía éxito» con todo sin evaluar →
  fail-fast (código 2) y código 3 si no se evalúa nada · `--out` dentro de un repo debe estar
  gitignoreado · errores de E/S y JSON → código 2 sin traceback · README sin promesas
  absolutas sobre secretos (best-effort explícito).
- **Careo r2 (Codex NO_APTO, 1 IMPORTANTE):** la comprobación de `--out` fallaba en
  ABIERTO si git daba error o timeout → fail-closed (solo se omite si git no está
  instalado) y `LC_ALL=C` para no depender del idioma de los mensajes de git.
