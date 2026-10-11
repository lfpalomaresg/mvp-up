# Notas de sesión — MVP-UP (código)

Formato por sesión: **Hecho · Pendiente · Decidido**. Todos los datos de tests y ejemplos son
sintéticos. Las notas de los loops 0-10 están en [`LOOPS.md`](LOOPS.md).

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
