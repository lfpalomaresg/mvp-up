# Plantilla de informe MVP-UP

Guardar como: `~/claude_workspace/AI_OS/PROJECTS/_escalado/<producto>/YYYY-MM-DD-informe.md`

```markdown
# MVP-UP · <Producto> · <YYYY-MM-DD>

**Modo:** express|full · **Etapa:** <etapa> · **Objetivo de valor:** <objetivo>
**Score global: X,X/10** (ponderado por objetivo) · Pasada nº <N>

## Scores por dimensión

| Dimensión | Score | Δ vs anterior | Estado |
|---|---|---|---|
| Técnica | 7/10 | +1 | 🟢 |
| Seguridad | 5/10 | = | 🟡 |
| ... | ... | ... | ... |
| (N/A o "sin evaluar" donde aplique) | — | — | ⚪ |

🟢 7-10 · 🟡 5-6 · 🔴 0-4 · ⚪ N/A

## Hallazgos estructurales
(los que bloquean varias dimensiones a la vez — máximo 3)

## Matriz impacto × esfuerzo

|  | Esfuerzo BAJO | Esfuerzo MEDIO/ALTO |
|---|---|---|
| **Impacto ALTO** | ⚡ QUICK WINS: ... | 🎯 APUESTAS: ... |
| **Impacto MEDIO/BAJO** | 📋 Si sobra tiempo: ... | 🗑️ Descartar: ... |

## Roadmap de escalado

### H1 — Esta semana (quick wins)
- [ ] <acción> · ~<horas/€> · sube <dimensión> · ejecutable por: Claude|operador|externo

### H2 — Este mes
- [ ] ...

### H3 — Trimestre
- [ ] ...

⚠️ Nota WIP: <si el producto no está en los carriles activos, indicarlo y marcar acciones como "encolar">

## Evolución (solo si hay pasada anterior)
- Acciones del roadmap anterior ejecutadas: X/Y
- Scores que subieron / bajaron y por qué
- Lección de la iteración

## Datos pendientes que el operador debe aportar
- ...

## TOP-5 propuesto para autorización
1. ...
```

**Reglas del informe:**
- Todo hallazgo cita su evidencia (archivo, URL, dato). Sin evidencia → fuera.
- Cifras económicas sin fuente → N/D, jamás estimaciones disfrazadas de datos.
- El informe es diagnóstico: no se ejecuta nada hasta que el operador autoriza el TOP-5.
