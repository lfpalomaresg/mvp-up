# MVP-UP 🚀

**Orquestador multi-agente de escalado de producto para Claude Code.**
Sube tu producto un nivel, esté en la etapa que esté.

> Una skill que audita cualquier producto, proyecto o servicio en **10 dimensiones** lanzando
> agentes de IA en paralelo, consolida los hallazgos en una **matriz impacto×esfuerzo** y te
> devuelve un **roadmap de escalado** priorizado. Y lo mejor: cada vez que la relanzas, compara
> con la pasada anterior y **mide tu progreso**. No es una foto — es un ciclo de mejora.

---

## ¿Qué problema resuelve?

Cuando construyes un producto (una app, un SaaS, incluso un servicio sin software) es fácil
mejorar solo lo que te gusta mejorar: el código, el diseño… mientras el pricing, lo legal,
la analítica o el proceso de venta se quedan a cero. MVP-UP te obliga a mirar **todo el
tablero a la vez** y te dice dónde está el siguiente punto de mayor palanca.

## Filosofía

1. **Solo análisis.** Los agentes nunca modifican nada: ni archivos, ni commits, ni APIs de pago.
2. **El humano autoriza.** MVP-UP diagnostica y propone un TOP-5; tú decides qué se ejecuta.
3. **Evidencia o nada.** Todo hallazgo cita su prueba (archivo, URL, dato). Las cifras
   económicas sin fuente se marcan N/D — jamás se inventan.
4. **Ciclo, no foto.** Los informes se versionan por fecha; cada re-auditoría muestra el Δ
   de cada score y qué acciones del roadmap anterior se hicieron (o se ignoraron).
5. **Coste consciente.** Disparo siempre manual. Tres modos: *express* por defecto (3-5
   dimensiones según la etapa), *full* (las 10, solo con confirmación) y *ligera* (1 agente
   para semillas, utilidades y proyectos congelados — score orientativo + 3 tareas de reanudación).

> **v1.1** — evoluciones tras calibración con 11 proyectos reales: modo ligera · el repo manda
> sobre la documentación en el intake · anclaje "salta al retomar" en la ficha del proyecto ·
> síntesis de cartera al auditar 2+ proyectos · verificación proporcional al tipo de entregable.

## Las 10 dimensiones

| # | Dimensión | Qué mira |
|---|---|---|
| 1 | **Técnica** | Código, arquitectura, deuda técnica, tests, ¿aguanta 10×? |
| 2 | **Seguridad** | Credenciales, auth, inputs, rate limiting, CVEs |
| 3 | **Legal** | RGPD, avisos legales, cookies, marca/IP, contratos, licencias |
| 4 | **Producto / UX** | Propuesta de valor en 5 segundos, fricción, onboarding, feature creep |
| 5 | **Comercial** | Oferta (estilo Grand Slam), pricing, garantías, canales, proceso de venta |
| 6 | **Marketing y hype** | Posicionamiento, ICP, motor de contenido, prueba social, narrativa |
| 7 | **Mercado** | Nicho, competencia con precios, hueco real, tendencias, riesgos |
| 8 | **Económica** | Costes recurrentes reales, margen unitario, break-even, ingresos |
| 9 | **Operativa** | Dependencia del fundador, procesos documentados, soporte, automatizable |
| 10 | **Datos y medición** | Analítica, las 3-5 métricas que importan, canal de feedback |

La nº 10 es la que cierra el ciclo: sin medición, los Δ entre auditorías son opinión.

## Cómo funciona

```
/mvp-up <producto> [express|full]
        │
        ▼
┌─ Fase 0 · INTAKE ──────────────────────────────────────────┐
│ Producto · Etapa (idea/MVP/producción/facturando)          │
│ Objetivo de valor: ¿más ingresos? ¿vendible? ¿inversión?   │
└────────────────────────────┬───────────────────────────────┘
                             ▼
┌─ Fase 1 · AGENTES EN PARALELO ─────────────────────────────┐
│ express: 3-5 dimensiones críticas de la etapa (agrupadas)  │
│ full:    10 agentes, uno por dimensión                     │
│ Cada uno → score 0-10 + hallazgos con evidencia            │
└────────────────────────────┬───────────────────────────────┘
                             ▼
┌─ Fase 2 · CONSOLIDACIÓN ───────────────────────────────────┐
│ Score global ponderado por el objetivo de valor            │
│ Matriz impacto × esfuerzo → quick wins primero             │
└────────────────────────────┬───────────────────────────────┘
                             ▼
┌─ Fase 3 · ROADMAP ─────────────────────────────────────────┐
│ H1 semana · H2 mes · H3 trimestre (coste estimado/acción)  │
└────────────────────────────┬───────────────────────────────┘
                             ▼
┌─ Fase 4 · COMPARACIÓN (si hay pasada anterior) ────────────┐
│ Δ por dimensión · acciones hechas vs ignoradas             │
└────────────────────────────┬───────────────────────────────┘
                             ▼
┌─ Fase 5 · ENTREGA ─────────────────────────────────────────┐
│ Informe fechado y versionado + TOP-5 → TÚ autorizas        │
└────────────────────────────────────────────────────────────┘
```

### Selección automática en modo express

| Etapa del producto | Dimensiones que audita |
|---|---|
| Idea / prototipo | mercado · producto/UX · comercial · económica |
| MVP funcionando | técnica · producto/UX · comercial · marketing/hype |
| Producción sin ingresos | marketing/hype · comercial · mercado · económica |
| Facturando | económica · operativa · seguridad · legal · datos |

## Estructura del repo

```
mvp-up/
├── README.md              ← estás aquí
├── index.html             ← página viva de la skill (ábrela en el navegador)
└── skill/
    ├── SKILL.md           ← la skill instalable (definición + proceso + edge cases)
    └── references/
        ├── dimensiones.md       ← prompt exacto de cada agente + rúbrica 0-10
        ├── plantilla-informe.md ← formato del informe versionado
        └── examples.md          ← 3 ejemplos + contraejemplos
```

## Implementación en código (`src/mvpup`)

Además de la skill, el repo contiene una implementación Python (≥3.11, núcleo sin
dependencias) del orquestador, para que el método sea reproducible y testeable:

| Módulo | Fase | Qué hace |
|---|---|---|
| `dimensions.py` | — | Catálogo FIJO: dimensiones, etapas, objetivos, tabla express, pesos ×2, parejas afines |
| `intake.py` | 0 | Intake validado (full exige confirmación explícita) |
| `selection.py` | 1 | Selección por etapa, N/A sin software, agrupación (express 3-5 agentes), lotes de 5 |
| `prompts.py` | 1 | Prompts por dimensión (copia literal de `dimensiones.md`), agrupados y ligera |
| `parsing.py` | 1 | Validador de headers EXACTOS + parser (completo, agrupado con rescate parcial, ligera) |
| `orchestrator.py` | 1 | Lotes ≤5, reintento con prompt reforzado, «sin evaluar», timeout por intento |
| `runners.py` · `anthropic_runner.py` | 1 | `FakeRunner` (tests y dry-run) y runner real con la API de Claude + instantánea del repo sin secretos |
| `dryrun.py` | 1 | Salidas sintéticas por dimensión para `run --dry-run`: toda la tubería sin red ni API key |
| `scoring.py` · `consolidation.py` | 2 | Score ponderado, matriz impacto×esfuerzo, hallazgos estructurales |
| `roadmap.py` | 3 | H1/H2/H3, backlog, apuestas no justificadas, regla WIP, TOP-5 |
| `compare.py` | 4 | Δ por dimensión, caídas en rojo, cambio de objetivo (recalcula), aviso >6 meses |
| `report.py` | 5 | Informe MD con los headers de la plantilla + JSON gemelo versionado |
| `portfolio.py` | 2 | Síntesis de cartera (2+ proyectos): patrones transversales, cobertura |
| `redaction.py` | — | Redacción best-effort de secretos (instantánea y mensajes de error) |
| `cli.py` | — | `mvpup plan` · `run` · `validate` · `cartera` |

### Uso

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev,anthropic]"
.venv/bin/pytest -q                                   # incluye la puerta de tipos (mypy)
.venv/bin/mypy --check-untyped-defs src               # o a mano

# Planificar (sin red, sin coste): selección, lotes, avisos y coste orientativo
mvpup plan --product "Mi producto" --stage mvp --objective ingresos --show-prompts

# Ensayo general (sin red, sin API key, sin coste): la pasada completa con datos sintéticos
mvpup run --product "Mi producto" --stage mvp --objective ingresos --dry-run

# Ejecutar con agentes reales (Sonnet por defecto; Fable/Mythos/Haiku bloqueados).
# En full con objetivo vendible/inversión, económica y comercial van con Opus (SKILL.md).
cp .env.example .env   # y rellena ANTHROPIC_API_KEY — .env está gitignoreado
mvpup run --product "Mi producto" --stage mvp --objective ingresos --repo ../mi-producto

# Opcional: anclar «⚡ MVP-UP X/10 — LEER AL RETOMAR» al final de la ficha del producto
mvpup run ... --ficha ruta/a/ficha.md --anclar

# Validar la salida de un agente lanzado a mano (p.ej. subagente de Claude Code)
mvpup validate salida.md --dims comercial,marketing

# Síntesis de cartera con los últimos informes de 2+ productos
mvpup cartera --save
```

Códigos de salida: `0` OK · `2` error de uso (intake, modelo vetado, falta la API key,
ficheros, `--timeout` no positivo, carpeta de informes no gitignoreada) · `3` pasada sin
ninguna dimensión evaluada · `130` interrumpida con Ctrl-C (no se guarda informe).

Los informes se guardan en `./informes/<producto>/YYYY-MM-DD-informe.md` (+ `.json`), o en
`--out` / `$MVPUP_REPORTS_DIR`. Si esa carpeta está dentro de un repo git, `run` exige que
esté en `.gitignore` (los informes pueden contener datos reales).

### Dry-run: ver la tubería entera sin gastar nada

`mvpup run --dry-run` recorre exactamente el mismo camino que una pasada real (selección por
etapa, agrupación en agentes, lotes de ≤5, parser, consolidación, matriz, roadmap, informe
versionado) pero sustituye a los agentes por un `FakeRunner` con salidas sintéticas. No abre
red, no lee `ANTHROPIC_API_KEY` y no cuesta tokens. Sirve para:

- comprobar una instalación nueva o un cambio de código de extremo a extremo;
- enseñar cómo es un informe antes de pagar una pasada;
- ensayar `--stage`, `--mode`, `--add/--remove`, `--no-software`… y ver qué dimensiones y lotes salen.

Lo que verás por `stderr`: el aviso `DRY-RUN`, el plan (dimensiones, N/A, `Lote 1: …`) y el log
de la pasada. Por `stdout`: la ruta del informe, el score global y el TOP-5. El informe:

- lleva una línea `**⚠️ DRY-RUN:** …` bajo el título y toda evidencia va marcada `[sintético]`;
- se guarda como `YYYY-MM-DD-dry-run.md` (+ `.json` con `"dry_run": true`): ese nombre **no**
  cuenta como pasada, así que no altera la numeración ni la comparación de la siguiente pasada
  real, y la síntesis de cartera lo ignora;
- los datos sintéticos están pensados para poblar los cuatro cuadrantes de la matriz, producir
  hallazgos estructurales y un dato pendiente compartido: no describen ningún producto.

`--dry-run` no se combina con `--runner fake` (ya simula los agentes) ni con `--anclar` (un
informe sintético nunca se ancla en una ficha real). Para simular respuestas concretas de agente
sigue existiendo `--runner fake --fake-responses <json>`.

### Cómo leer el informe

El Markdown conserva los headers exactos de `skill/references/plantilla-informe.md`, en este orden:

1. **Cabecera** — producto, fecha, modo, etapa, objetivo de valor y **score global** (media
   ponderada: las dimensiones con peso ×2 para ese objetivo cuentan doble; N/A y «sin evaluar»
   no cuentan) con el nº de pasada.
2. **Scores por dimensión** — una fila por dimensión seleccionada: score sobre 10, Δ frente a la
   pasada anterior (`+1`, `=`, `🔴 -2`, `nuevo`, o `n/c (8→6)` si cambió el objetivo de valor) y
   semáforo 🟢 7-10 · 🟡 5-6 · 🔴 0-4 sobre el score tal como se muestra. `N/A` = no aplica
   al producto; `sin evaluar` = el agente falló dos veces (ver «Datos pendientes»).
3. **Hallazgos estructurales** — el mismo problema citado por 2+ dimensiones (máximo 3). Son
   candidatos detectados por solapamiento léxico, no un juicio: revísalos primero porque una
   acción sube varias dimensiones a la vez.
4. **Matriz impacto × esfuerzo** — TODOS los hallazgos con evidencia, en su cuadrante: ⚡ quick
   wins (impacto alto, esfuerzo bajo), 🎯 apuestas (alto / medio-alto), 📋 si sobra tiempo
   (medio-bajo / bajo) y 🗑️ descartar. Dentro de cada celda, primero los de mayor impacto y de
   dimensiones prioritarias para tu objetivo.
5. **Roadmap de escalado** — H1 (esta semana) = quick wins · H2 (este mes) = apuestas de
   esfuerzo medio y «si sobra tiempo» de impacto medio · H3 (trimestre) = apuestas de esfuerzo
   alto **solo** si su dimensión pesa ×2 para el objetivo; el resto queda listado como «no
   justificadas». Coste `~N/D` y «ejecutable por: por decidir» no se inventan. Una acción
   estructural se fusiona en una sola línea que «sube A + B». Fuera de carriles WIP todo va
   marcado «encolar».
6. **Evolución** — solo con pasada anterior: score anterior, caídas en 🔴 con causa probable
   (hallazgos de impacto alto nuevos, con evidencia), acciones del roadmap anterior que ya no
   aparecen («✅? candidatas a hechas», a confirmar) y avisos (>6 meses, cambio de etapa u
   objetivo, campos ilegibles del JSON anterior).
7. **Datos pendientes que el operador debe aportar** — lo que los agentes pidieron (deduplicado
   entre dimensiones), los hallazgos que un agente citó **sin evidencia** y por eso se quitaron,
   y las dimensiones a re-evaluar.
8. **TOP-5 propuesto para autorización** — estructurales primero, luego H1→H3. Nada se ejecuta
   hasta que lo autorices.

El `.json` gemelo guarda lo mismo de forma estructurada (`scores`, `findings`, `roadmap`,
`top`, `log`); es lo que lee la pasada siguiente para calcular los Δ y lo que usa `cartera`.
Si un agente devolvió un formato que el parser no acepta, el log de la pasada dice qué faltó o
qué línea estaba mal (por ejemplo, un `## Score: ?/10` o un `[H2]` ilegible) y la dimensión se
reintentó una vez con el prompt reforzado antes de quedar «sin evaluar».

Secretos: la API key solo en `.env` (gitignoreado) o en el entorno. Los agentes reales no
tienen herramientas: reciben una instantánea de solo lectura del repo que **no sigue
symlinks**, excluye ficheros y carpetas con nombre de secreto (`.env`, `*.pem`,
`credentials/`…) y **redacta** patrones de claves, asignaciones sensibles (`api_key=…`,
`"token": "…"`) y credenciales en URLs. Es protección *best-effort*, no una garantía: no
audites con agentes de la API un repo con secretos incrustados de forma exótica sin
revisarlo antes. Los tests usan datos ficticios.
Bitácora de construcción y careos: [`docs/LOOPS.md`](docs/LOOPS.md).

## Instalación

1. Requiere [Claude Code](https://claude.com/claude-code).
2. Copia la carpeta de la skill:
   ```bash
   cp -r skill ~/.claude/skills/strategy-mvp-up
   ```
3. Abre una sesión de Claude Code y escribe `/mvp-up <tu-producto>`.

### Adaptación (importante)

La skill original guarda los informes en la carpeta de conocimiento del autor
(`~/claude_workspace/AI_OS/PROJECTS/_escalado/`) y lee contexto de negocio de sus fichas de
proyecto. Antes de usarla, **edita `skill/SKILL.md` y cambia esas rutas por las tuyas**
(cualquier carpeta donde quieras versionar los informes vale). También menciona skills
auxiliares del ecosistema del autor (`tool-quality-gate`, `tool-site-audit`,
`strategy-research`…): si no las tienes, los agentes hacen el análisis igualmente con sus
propios checklists — esas skills solo enriquecen el resultado.

## Cuándo NO usarla

- «Revisa la seguridad de mi web» → usa una auditoría de seguridad específica.
- «¿Está listo para deploy?» → usa un quality gate técnico.
- Chequeos puntuales de una sola cosa → MVP-UP es la vista 360°, no un linter.

## Estado

- ✅ v1.1 (2026-07) — calibrada con 11 proyectos reales (1 piloto express + 3 express + 7 ligeras, 18 agentes)
- 🔬 Autoevaluada con su propio modo ligera: 6/10 (sí, se audita a sí misma)
- 📝 Roadmap v1.2: validador de formato de outputs · tabla completa de ponderaciones por objetivo de valor · límites operativos y coste por modo documentados
- 🐍 Implementación Python 0.2.0 (2026-10): núcleo completo + CLI, 300+ tests, construida en 10 loops de automejora con revisión adversarial (Codex/Gemini) — bitácora en [`docs/LOOPS.md`](docs/LOOPS.md)
- 🧪 Loop 11 (2026-10-11): `run --dry-run` de extremo a extremo, parser con fallo cerrado y mensajes explícitos, puerta de tipos con mypy — notas en [`docs/10_SESSION_NOTES.md`](docs/10_SESSION_NOTES.md)

## Autor y créditos

**Luisfran Palomares** — dirección hotelera + IA aplicada.
Creada con Claude Code sobre el patrón de skills de iAmasters OS.

MVP-UP nació dentro de **[Blindbeds](https://blindbeds.com)** — IA aplicada a la operación
real del hotel — como la metodología con la que auditamos y escalamos nuestros propios
productos (APPCC, Supply) antes de abrirla a cualquier proyecto.
