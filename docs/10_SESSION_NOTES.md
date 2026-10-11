# Notas de sesión — MVP-UP (código)

Formato por sesión: **Hecho · Pendiente · Decidido**. Todos los datos de tests y ejemplos son
sintéticos. Las notas de los loops 0-10 están en [`LOOPS.md`](LOOPS.md).

## 2026-10-11 (ronda 2) — Comparar pasadas, HTML autocontenido, ficha con frontmatter, 6 loops

**Rama:** `claude/mvp-up-compare-reports-2ff53c` (desde `main` en `4903127`, el squash del PR #1).
**Suite antes:** 321 tests en verde · mypy `--check-untyped-defs`: 0 errores en 20 ficheros.
**Suite después:** 357 tests en verde · mypy: 0 errores en 22 ficheros con la configuración más
estricta de `pyproject` (`disallow_any_generics`, `warn_return_any`, `disallow_untyped_defs`,
`disallow_incomplete_defs`). Solo ejecutado con Python 3.13 (el único disponible aquí).

### Hecho

1. **`mvpup compare <anterior> <nuevo>`** (`compare.py`, `cli.py`): `diff_reports()` compara los
   JSON gemelos de dos informes guardados (se acepta la ruta del `.md` o del `.json`) y
   `render_diff()` escribe el resumen Markdown: tabla Δ por dimensión con el mismo formato que el
   informe, acciones **cerradas** (del roadmap anterior y ya ni acción ni hallazgo: candidatas a
   hechas, «✅?»), **nuevas** («🆕») y que **siguen abiertas** («⏳»), y avisos: productos distintos,
   argumentos en orden invertido, DRY-RUN, >6 meses, cambio de etapa, cambio de objetivo (Δ «n/c» y
   score anterior recalculado con los pesos nuevos), campos ilegibles. `--save <ruta>` guarda en vez
   de imprimir. `compare_with_previous` (la Evolución de `run`) comparte ahora con `diff_reports`
   los lectores tolerantes del JSON y los avisos de contexto (sin duplicar lógica). Tests: función
   pura con dicts sintéticos + CLI con dos informes generados por `run --dry-run` (uno con
   `--add seguridad --remove marketing` y un score retocado para que haya Δ real).
2. **Informe HTML autocontenido** (`htmlreport.py`, `cli.py`): conversor Markdown→XHTML sin
   dependencias para el subconjunto que generan `report`, `compare` y `portfolio` (headers,
   párrafos, negrita, código, enlaces, listas anidadas, casillas `- [ ]`, numeradas, citas, tablas).
   CSS en línea; ningún `script`, `link`, `img`, `iframe`, fuente ni `url()`. La matriz impacto ×
   esfuerzo es una tabla accesible (`caption`, `th scope="col"/"row"`, cada cuadrante como etiqueta
   + `<ul>` en vez de `<br>`). `mvpup html <md> [--out]` y `run --html`. Tests: el HTML se parsea
   con `xml.etree` (bien formado) y se inventarían todas las etiquetas y atributos `src/href`.
3. **`--ficha <ruta.md>` con frontmatter** (`ficha.py`, `cli.py`): `anchor_frontmatter()` escribe
   `mvpup_date`, `mvpup_score` y `mvpup_report` en el frontmatter YAML editando línea a línea (sin
   parser YAML): el resto del frontmatter y el cuerpo quedan byte a byte (CRLF, BOM, comentarios,
   orden), las claves se sustituyen en su sitio o se añaden al final, duplicados se eliminan, una
   fence inicial sin cerrar se trata como cuerpo, ficha inexistente → mínima. Idempotente por
   informe (segunda llamada → `False`, bytes idénticos). `--anclar` sigue siendo opt-in para el
   bloque visible. Tests de idempotencia, contenido ajeno intacto, CRLF/BOM, ruta con comillas y
   barras, y CLI (incluido que `--dry-run` nunca toca la ficha).
4. **6 loops de automejora** (cada uno con test en rojo previo y commit propio, `tests/test_loops_round2.py`):
   1. `cli.py`: `--fake-responses` sin `--runner fake` se ignoraba y la pasada salía con agentes
      REALES → error de uso (código 2) antes de construir ningún runner.
   2. `cli.py`: `validate` sin `--dims` y `--runner fake` sin `--fake-responses` salían con
      `SystemExit(msg)` (código 1, sin «Error:») → `CliError` (código 2); `CliError` declarada
      antes de su primer uso.
   3. `cli.py`: una pasada con cero dimensiones evaluadas (código 3) anclaba igualmente la ficha
      (frontmatter + bloque con «—/10») → la comprobación va antes de tocar la ficha y lo dice;
      anclajes extraídos a `_anchor()`.
   4. Tipos: `pyproject` activa `disallow_any_generics`, `warn_return_any`, `disallow_untyped_defs`
      y `disallow_incomplete_defs` (la puerta `tests/test_typing.py` y CI lo heredan) → 3 errores
      corregidos (`_canonical` tipado, `to_json -> dict[str, Any]`, `main()` sin devolver `Any`).
   5. Legibilidad: tres formateadores de score distintos (`report.fmt_score`, `compare._fmt`,
      `portfolio._fmt`) con salidas inconsistentes (la Evolución decía «6/10» y la cabecera
      «6,0/10») → un único `scoring.fmt_score`.
   6. Legibilidad: `anchor_ficha` vivía en `report.py` y escribía siempre `\n` → movido a
      `ficha.py` junto al frontmatter, conserva el salto de línea de la ficha (CRLF/LF).
5. **Docs**: README (tabla de módulos, uso, sección «Comparar pasadas, HTML y ficha», estado),
   `LOOPS.md` (Loop 12), esta nota.

### Pendiente (operador)

- Ejecutar `mvpup compare` sobre dos pasadas REALES del mismo producto para calibrar si la
  heurística «cerrada = ya no aparece ni como acción ni como hallazgo» acierta lo suficiente
  (aquí solo se ha probado con datos sintéticos).
- Abrir un HTML generado en los navegadores que uses (y en impresión): el CSS es deliberadamente
  mínimo; no se ha probado en navegador real en esta sesión.
- CI: verificar que la configuración más estricta de mypy pasa en 3.11 y 3.12 (aquí solo 3.13).
- `.claude/settings.json` sigue invocando `graphify hook-guard`, inexistente aquí; no se ha tocado.

### Decidido

- `--ficha` **sin** `--anclar` ahora escribe (solo el frontmatter). Antes `--ficha` únicamente
  alimentaba el prompt del modo ligera. La tarea pedía «modo `--ficha`: anclar la pasada», y el
  frontmatter es no destructivo. Si se prefiere que también sea opt-in, es un flag de una línea
  (ver «Decisiones que dejo al operador» en el PR).
- Claves del frontmatter planas y en inglés (`mvpup_date`, `mvpup_score`, `mvpup_report`): un
  bloque anidado `mvpup:` obligaría a un parser YAML o a reescribir el frontmatter; planas se
  editan línea a línea sin tocar nada ajeno. `mvpup_score` es número YAML (`6.2`) o `null`.
- «Acción cerrada» en `compare` = del roadmap anterior y ausente del roadmap **y** de los hallazgos
  del nuevo; si solo salió del roadmap pero sigue siendo hallazgo, está «abierta». Nunca se afirma
  que se hizo: el operador confirma.
- `compare` avisa, no rechaza, cuando los informes son de productos distintos, van en orden
  invertido o son DRY-RUN: el operador eligió esos ficheros a propósito.
- El HTML se genera desde el Markdown (no desde el `Report`): así sirve también para la
  comparación, la cartera y cualquier informe antiguo. Sin resaltado de código ni fuentes web por
  diseño (autocontenido real).
- No se ha añadido ninguna dependencia (ni YAML ni Markdown): el núcleo sigue a cero.

### Revisión del PR #2 (careo nivel 1 con Codex, ejecución local en el Mac)

- Base verificada: la rama parte de `4903127` (= `main` con el PR #1 ya fusionado por squash); sin
  fusión necesaria. 357 tests en verde y mypy a 0 antes de tocar nada.
- Ejecutado de verdad: dos dry-runs + `compare` (ruta `.md` y `.json`, `--save`, orden invertido,
  errores de uso), `html` del informe y de la comparación (XML bien formado con `xml.etree` y
  `xmllint`; 0 `http`, 0 `script/link/img/@import/url(`), `--ficha` dos veces sobre una ficha
  ajena con BOM + CRLF (cuerpo byte a byte, comentario y orden conservados, idempotente).
- Hallazgos corregidos (test rojo visto antes de cada fix):
  1. `htmlreport.py`: `[x](javascript:…)` o `data:` en texto del modelo acababa como `<a href>` en
     un HTML «sin JS». Solo `http(s):`, `mailto:` y destinos relativos se enlazan; el resto queda
     como texto (hallazgo propio, confirmado por Codex: severidad alta).
  2. `ficha.py`: frontmatter con CRLF y LF mezclados no reconocía el cierre y anteponía un
     segundo frontmatter (Codex, media). `_split` trocea ahora por `\r\n|\n` sin perder bytes.
  3. `ficha.py`: un cierre `...` se reescribía como `---` (Codex, baja). Se conserva.
  4. `htmlreport.py` (rondas 2-3 del careo): `\x01javascript:` eludía el filtro (un navegador
     descarta los controles iniciales) y U+0001/U+FFFE rompían el XHTML. Se eliminan controles
     C0/DEL/C1 y no-caracteres de todo el texto (y del `<title>`) antes de escapar.
- Descartado con motivo: ninguno. Heredado/por diseño: una regla horizontal `---` en la primera
  línea se interpreta como frontmatter (heurística habitual, no destructiva); claves `mvpup_*`
  planas duplicadas se consolidan en una.

## 2026-10-11 — Dry-run, parser con fallo cerrado, 8 loops de automejora

**Rama:** `claude/dry-run-pipeline-ngeroq` (desde `main` en `07880c5`).
**Suite antes:** 241 tests en verde · mypy `--check-untyped-defs`: 9 errores en 5 ficheros.
**Suite después:** 311 tests en verde (incluye la puerta de tipos) · mypy: 0 errores en 20 ficheros.

### Hecho

1. **`mvpup run --dry-run`** (`dryrun.py`, `cli.py`, `report.py`): la pasada completa con un
   `FakeRunner` alimentado por salidas sintéticas por dimensión (válidas con la plantilla completa
   y la ligera; cuatro cuadrantes poblados; un hallazgo compartido que sale como estructural; un
   dato pendiente compartido). Sin red, sin `ANTHROPIC_API_KEY`, sin tocar `_runner`. El informe
   lleva aviso `DRY-RUN`, evidencias `[sintético]`, JSON con `dry_run: true` y nombre
   `YYYY-MM-DD-dry-run` (no cumple `REPORT_NAME_RE`: nunca cuenta como pasada ni entra en la
   cartera, que además rechaza `dry_run`). Incompatible con `--runner fake` y `--anclar`. `run`
   imprime ahora el plan (dimensiones, N/A, lotes) por `stderr`. Test extremo a extremo por CLI que
   bloquea `socket` y valida los headers de la plantilla en orden, la matriz, el TOP-5 y el JSON;
   parametrizado por etapa, full, ligera y servicio sin software.
2. **Parser con fallo cerrado** (`parsing.py`, `orchestrator.py`, `report.py`). La tarea hablaba
   de JSON; la salida de los agentes es Markdown con headers `##`, así que se aplicó el mismo
   criterio a ese formato:
   - *texto antes/después*: prosa, fences, envoltorio XML, CRLF y BOM se toleran sin perder nada
     (BOM era el único que fallaba);
   - *campos ausentes / salida parcial*: cualquier línea con `[Hn]` que no se lea (numerada, en
     negrita, sin `Esfuerzo`, nivel inventado) es error de formato y se reintenta; antes una
     `2. [H2] …` se descartaba en silencio. Una dimensión cuyos hallazgos se descartaron todos por
     falta de evidencia es también error de formato (antes llegaba al informe con score y cero
     hallazgos);
   - *scores fuera de 0-10*: `-2/10` dice «fuera de rango» (antes «falta el header»); `?/10`,
     `7/5`, `alto` o un header con texto cambiado citan la línea encontrada; separadores agrupados
     escritos como `## Dimensión:` reciben una pista explícita;
   - *nunca un informe silenciosamente incompleto*: los `warnings` del parser (hallazgos citados sin
     evidencia) ahora van al log de la pasada y al informe (sección «Datos pendientes»; en ligera,
     bajo los hallazgos). Una respuesta no textual del runner se registra como fallo del agente en
     vez de tumbar la pasada con `AttributeError`.
3. **8 loops de automejora** (cada uno con test en rojo previo, commit propio):
   1. `compare.py`: campos con tipo corrupto en el JSON anterior (`global_score: "alto"`,
      `scores: "x"`, acción no textual…) reventaban `build_report` **después** de pagar la pasada →
      se ignoran y se listan en Evolución; red de seguridad en `build_report`; tipos limpios.
   2. `roadmap.py`: `Horizon.title` pisaba `str.title` → `Horizon.label` + tabla `HORIZON_LABELS`.
   3. `cli.py`: `--timeout` 0/negativo/NaN se validaba al fallar cada agente → error de uso previo.
   4. `cli.py`: `cost_hint` con 0 agentes decía «≈ 0-0k tokens» → «sin agentes que lanzar».
   5. `report.py`: el semáforo se calculaba sobre el score crudo y la tabla lo muestra redondeado
      (`6,96` → «7,0/10 🟡») → semáforo sobre el valor mostrado.
   6. `runners.py`: `FakeRunner` acepta cualquier valor y fallaba al ejecutar → valida al construir
      (nombra la clave); la CLI lo convierte en código 2 antes de lanzar.
   7. `cli.py`/`orchestrator.py`: Ctrl-C mostraba traceback → código 130 con mensaje; el resultado
      del hilo de agente es un dataclass tipado sin `type: ignore`.
   8. Puerta de tipos: `tests/test_typing.py` ejecuta `mypy --check-untyped-defs src` (se salta si
      no está instalado), mypy en el extra `dev`, en `pyproject` y en el workflow de CI; últimos
      errores de tipos corregidos.
4. **README**: sección «Dry-run» y «Cómo leer el informe», códigos de salida nuevos, fila de
   `dryrun.py`.

### Pendiente (operador)

- Ejecutar una pasada real con el runner de la API para confirmar que los mensajes nuevos del
  parser mejoran el reintento con prompt reforzado (aquí no se ha usado ninguna clave).
- Decidir si una dimensión con score válido y **cero** `[Hn]` (sin ninguno citado) debe aceptarse
  (hoy sí) o reintentarse como la ligera (que exige 3-5).
- CI: el paso de mypy se añadió al workflow; verificar que pasa en 3.11 y 3.12 (aquí solo se ha
  ejecutado con 3.13).
- `.claude/settings.json` sigue invocando `graphify hook-guard`, que no existe en este entorno; no
  se ha tocado.

### Decidido

- El dry-run **escribe** el informe en la carpeta de informes (misma comprobación de `.gitignore`
  que una pasada real) en vez de imprimirlo: así se ve el fichero real con su JSON gemelo. Se aísla
  por nombre de fichero, no por carpeta.
- El dry-run no compara con pasadas anteriores (siempre «Pasada nº 1 · línea base») para no mezclar
  datos sintéticos con un histórico real.
- «Fallo cerrado» en el parser significa *error de formato → reintento → «sin evaluar»*, nunca
  adivinar: no se aceptan hallazgos numerados ni se infiere un score; se explica qué se encontró.
- Las salidas sintéticas llevan `[sintético]` en cada evidencia además del aviso de cabecera, para
  que un fragmento copiado fuera del informe siga delatándose.
- No se ha añadido linter (ruff) ni se han tocado dependencias de ejecución: el núcleo sigue sin
  dependencias; mypy es solo del extra `dev`.
