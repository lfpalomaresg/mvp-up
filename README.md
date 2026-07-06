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
5. **Coste consciente.** Disparo siempre manual. Modo *express* por defecto (3-5 dimensiones
   según la etapa); modo *full* (las 10) solo con confirmación.

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

- ✅ v1 funcional (2026-07)
- 🔬 En calibración con producto piloto real
- 📝 Roadmap: ponderaciones afinadas por objetivo de valor tras 3+ pasadas reales

## Autor

**Luisfran Palomares** — dirección hotelera + IA aplicada.
Creada con Claude Code sobre el patrón de skills de iAmasters OS.
