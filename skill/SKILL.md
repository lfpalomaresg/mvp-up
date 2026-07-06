---
name: strategy-mvp-up
description: >-
  Orquestador MVP-UP — audita un producto, proyecto o servicio en 10 dimensiones (técnica,
  seguridad, legal, UX, comercial, marketing/hype, mercado, económica, operativa, datos)
  con agentes paralelos de solo análisis; consolida scores 0-10, matriz impacto×esfuerzo
  y roadmap; cada pasada compara con la anterior. Activar con '/mvp-up', 'escala este
  producto', 'auditoría 360'. Modos: express (default), full (10 agentes), ligera
  (semillas, 1 agente). Con 2+ proyectos genera además síntesis de cartera.
triggers:
  - "/mvp-up"
  - "mvp up"
  - "escala este producto"
  - "auditoría 360"
  - "sube de nivel este proyecto"
  - "cómo escalo este producto"
  - "audita mi producto en todos los aspectos"
alwaysActive: false
---

# MVP-UP — Orquestador de escalado de producto

> **v1.2 (2026-07-07)** — validador de formato, tabla completa de ponderaciones, límites operativos y coste documentados (salidas de la autoevaluación 6/10). **v1.1 (2026-07-06)** — evoluciones tras la campaña de calibración real de 11 proyectos.

Convierte cualquier producto, proyecto o servicio en un diagnóstico 360° + roadmap de escalado,
lanzando **agentes paralelos de solo análisis** (uno por dimensión en modo full, agrupados en express).
Cada re-ejecución compara contra el informe anterior: el escalado es un ciclo, no una foto.

**Filosofía:** los agentes NUNCA modifican nada. MVP-UP diagnostica, prioriza y propone;
el operador autoriza qué se ejecuta (coherente con AI_RULES: coste mínimo + autorización previa).

---

## Cuándo se invoca

- `/mvp-up <producto> [express|full]` — invocación directa
- "escala este producto", "auditoría 360 de X", "sube de nivel este proyecto"
- **Modo RADAR** (sugerencia, nunca auto-lanzamiento): al cerrar un hito de un producto,
  antes de un deploy importante, o cuando un producto empiece a facturar, sugerir:
  «¿Lanzo /mvp-up express sobre <producto>?» — el botón siempre lo pulsa el operador.

**NO se dispara nunca automáticamente** (ni por push, ni por cron). Es la operación más cara
del ecosistema; el pre-deploy técnico ya lo cubre `tool-quality-gate`.

---

## Process

### Fase 0 · Intake (2-5 min, sin agentes)

Recopilar antes de lanzar nada:

1. **Producto**: nombre, ruta del repo/carpeta, URL si está desplegado, ficha en `~/claude_workspace/AI_OS/PROJECTS/<producto>.md` (leerla si existe).
   ⚠️ **El repo manda sobre la ficha**: verificar `git log` y estructura real ANTES de fiarse de la ficha; si divergen, usar el estado del repo y reportar la desalineación como hallazgo estándar del informe (proponiendo actualizar la ficha). Lección de calibración: las fichas suelen estar desactualizadas.
   Si NO existe ficha: no improvisar contexto — auditar solo el repo, y al cerrar la pasada crear la ficha mínima (3 líneas: qué es, estado, repo) con su anclaje ⚡ incluido.
2. **Etapa**: idea/prototipo · MVP funcionando · en producción sin ingresos · facturando.
3. **Objetivo de valor** (pregunta clave): ¿qué significa "escalarlo"? → más ingresos / producto vendible a terceros / atraer inversión / reducir dependencia del operador. La ponderación de scores depende de esto.
4. **Modo**: express (default) · full · **ligera**. Full: confirmar antes («son 10 agentes en paralelo, la pasada cara»). **Ligera** — para semillas, utilidades y proyectos congelados fuera de los carriles WIP: 1 solo agente multi-dimensión, informe reducido (score orientativo + estado real vs ficha + 3-5 hallazgos + valor potencial + 3 tareas de reanudación); plantilla en `references/dimensiones.md` § "Modo ligera".
5. **Pasada anterior**: comprobar si existe `AI_OS/PROJECTS/_escalado/<producto>/` con informes previos.

**Selección de dimensiones en express** (según etapa):

| Etapa | Dimensiones críticas |
|---|---|
| Idea/prototipo | mercado · producto/UX · comercial · económica |
| MVP funcionando | técnica · producto/UX · comercial · marketing/hype |
| Producción sin ingresos | marketing/hype · comercial · mercado · económica |
| Facturando | económica · operativa · seguridad · legal · datos |

El usuario puede añadir/quitar dimensiones antes de lanzar.

### Fase 1 · Lanzar agentes en paralelo

- **Full**: 10 agentes (uno por dimensión). **Express**: 3-5 agentes según tabla anterior.
- Cada agente recibe su prompt de `references/dimensiones.md` (bloque de su dimensión + plantilla común) rellenando: producto, ruta, URL, etapa, objetivo de valor, contexto AI_OS.
- Agentes de **solo lectura/análisis**: prohibido editar archivos, hacer commits o llamar APIs de pago sin avisar.
- Cada agente devuelve el formato estándar: score 0-10 + hallazgos (máx 7, con impacto A/M/B y esfuerzo A/M/B) + quick wins + riesgos.
- **Validador de formato (obligatorio):** al recibir cada output, comprobar que contiene los headers `##` EXACTOS de su plantilla (completa o ligera); si falta alguno → un reintento con prompt reforzado (misma regla que para fallos de contenido). El MISMO check aplica al orquestador en la consolidación: los informes finales conservan los headers de sus plantillas — el orquestador NO condensa ni reinventa el formato (lección de autoevaluación: el primer incumplimiento real lo cometió el orquestador, no un agente).
- **Límites operativos:** máximo 5 agentes en paralelo por lote (full = 2 lotes de 5). Coste orientativo medido en la calibración 2026-07 (agentes Sonnet): ligera ≈ 60-80k tokens · express ≈ 250-400k · full ≈ ~1M. Recordar modo y coste al usuario antes de lanzar full.
- Si una dimensión no aplica (p.ej. "técnica" en un servicio sin software como un spa), no lanzar su agente y marcar N/A en el informe.

**Política de modelos (jerarquía por capas):**

| Capa | Modelo | Por qué |
|---|---|---|
| Orquestador (esta sesión) | El heredado — debe ser tier frontera (Fable/Opus) | Intake, ponderación, cruce de hallazgos y roadmap: donde el criterio importa |
| Agentes de dimensión | `model: sonnet` en la llamada Agent | Trabajo acotado con checklist; rendimiento casi igual a fracción de coste ×3-10 agentes |
| Full + decisión crítica (venta, inversión, socio) | Económica y comercial con `model: opus`; resto sonnet | Los 2 agentes de más juicio en la pasada que más importa |
| Nunca | Haiku/tier ligero para agentes | Evaluar impacto/esfuerzo requiere juicio; ahí se queda corto |

Regla portable (si se ejecuta el método fuera de Claude): orquestador = modelo frontera con
razonamiento del proveedor; agentes = tier medio; jamás el tier mini/ligero. Equivalencias
en `AI_OS/WORKFLOWS.md`.

### Fase 2 · Consolidación

1. Recoger los outputs de todos los agentes; normalizar formato.
2. **Score global** = media ponderada de las dimensiones evaluadas, con multiplicador ×2 en las prioritarias del objetivo de valor (tabla FIJA — no inventar pesos por sesión, rompe la comparabilidad Δ):

   | Objetivo de valor | Dimensiones con peso ×2 |
   |---|---|
   | Más ingresos | comercial · marketing/hype · económica |
   | Vendible a terceros | legal · técnica · operativa |
   | Atraer inversión | mercado · económica · datos y medición |
   | Reducir dependencia del operador | operativa · datos y medición · producto/UX |

   ⚠️ Si el objetivo de valor CAMBIÓ respecto a la pasada anterior: recalcular el score anterior con los pesos nuevos cuando sea posible, y en todo caso marcar los Δ como **"no comparables directamente"** explicando el cambio en el informe.
3. **Matriz impacto×esfuerzo** con TODOS los hallazgos: cuadrante quick wins (impacto A, esfuerzo B) primero.
4. Detectar hallazgos que se refuerzan entre dimensiones (p.ej. "sin analítica" bloquea comercial Y marketing) → marcarlos como estructurales.
5. **Si la pasada cubre 2+ proyectos**: generar además la síntesis de CARTERA — patrones transversales que ningún informe individual muestra (p.ej. "técnica siempre > comercial", "la ventaja competitiva del operador sin capitalizar en ningún proyecto") — e incluirla en la entrega y en memoria.

### Fase 3 · Roadmap de escalado

Tres horizontes, cada acción con coste estimado (horas/€) y a qué dimensión sube el score:
- **H1 — Esta semana**: quick wins.
- **H2 — Este mes**: mejoras de fondo con ROI claro.
- **H3 — Trimestre**: apuestas estratégicas (solo si el objetivo de valor las justifica).

Respetar la regla WIP del foco estratégico: si el producto no está en los carriles activos, el roadmap lo dice explícitamente y recomienda encolar, no ejecutar.

### Fase 4 · Comparación con pasada anterior (si existe)

- Leer el último informe de `AI_OS/PROJECTS/_escalado/<producto>/`.
- Tabla de evolución: score por dimensión anterior → actual, con Δ.
- Qué acciones del roadmap anterior se hicieron / se ignoraron, y si movieron el score.
- Si un score BAJÓ, señalarlo en rojo con causa probable.

### Fase 5 · Entrega y cierre

1. Informe MD → `~/claude_workspace/AI_OS/PROJECTS/_escalado/<producto>/YYYY-MM-DD-informe.md` (portable, lo lee cualquier IA; sincroniza Mac↔HP por Drive). Verificación inline obligatoria: todo hallazgo con evidencia; cifras sin fuente = N/D.
2. **Anclaje "salta al retomar"** (cierra el ciclo): añadir sección `## ⚡ MVP-UP X/10 (fecha) — LEER AL RETOMAR` al final de la ficha `AI_OS/PROJECTS/<producto>.md` apuntando al informe, y a la memoria del proyecto si existe (+ línea en MEMORY.md). La próxima sesión sobre ese proyecto DEBE arrancar leyendo el informe.
3. Si el usuario quiere compartir el informe: HTML autocontenido vía `tool-visual-explainer`, y SOLO en ese caso pasar `tool-output-verifier` (gate para entregables de cliente; para informes internos MD basta la verificación inline del punto 1).
4. Presentar al usuario el TOP-5 de acciones y preguntar cuáles autoriza. **Nada se ejecuta sin OK.**
5. Si autoriza acciones ejecutables por Claude, proponer orden y arrancar (o encolar para próxima sesión).
6. Append en `context/learnings.md` bajo `## strategy-mvp-up` si la pasada enseñó algo del método.

---

## Outputs

- `AI_OS/PROJECTS/_escalado/<producto>/YYYY-MM-DD-informe.md` — informe versionado (scores, matriz, roadmap, evolución)
- (Opcional) HTML compartible del informe
- TOP-5 de acciones propuestas en la conversación, pendientes de autorización

## Skills que llama

- `tool-quality-gate` — insumo del agente de dimensión técnica (si hay repo web)
- `tool-site-audit` — insumo de los agentes de seguridad y legal (si hay URL desplegada)
- `strategy-research` — insumo del agente de mercado
- `marketing-positioning` / `marketing-icp` — contexto para el agente de marketing (leer sus outputs si existen, no relanzarlas)
- `tool-visual-explainer` — informe HTML compartible
- `tool-output-verifier` — gate de calidad antes de entregar

## Edge cases

- **Producto sin software** (servicio, p.ej. un spa): omitir agentes técnica/seguridad-código; legal y operativa usan la variante "servicio" de `references/dimensiones.md`.
- **Sin datos económicos**: el agente económico NO inventa cifras; marca N/D, lista qué datos pedir al operador y puntúa solo lo verificable.
- **Producto fuera de los carriles activos (regla WIP)**: la auditoría se hace igual, pero el roadmap marca las acciones como "encolar" salvo autorización explícita.
- **El usuario pide lanzarlo automático/cron**: recordar la filosofía (caro + AI_RULES) y ofrecer alternativa: recordatorio de re-auditoría en el wrap-up o cita trimestral.
- **Un agente falla o devuelve formato inválido**: reintentar una vez con el prompt reforzado; si vuelve a fallar, marcar la dimensión como "sin evaluar" y seguir — el informe nunca se bloquea por una dimensión.
- **Informe anterior de hace >6 meses**: avisar de que la comparación puede no ser significativa (el producto pudo cambiar de etapa).
