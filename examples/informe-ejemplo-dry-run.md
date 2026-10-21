# MVP-UP · Ejemplo SaaS de reservas · 2026-10-21

**⚠️ DRY-RUN:** agentes simulados con datos sintéticos (evidencias marcadas `[sintético]`). Este informe NO es una auditoría y no cuenta como pasada.
**Modo:** express · **Etapa:** mvp · **Objetivo de valor:** ingresos
**Score global: 4,7/10** (ponderado por objetivo) · Pasada nº 1

## Scores por dimensión

| Dimensión | Score | Δ vs anterior | Estado |
|---|---|---|---|
| Técnica | 6/10 | — | 🟡 |
| Producto / UX | 7/10 | — | 🟢 |
| Comercial | 4,5/10 | — | 🔴 |
| Marketing y hype | 3/10 | — | 🔴 |

🟢 7-10 · 🟡 5-6 · 🔴 0-4 · ⚪ N/A

## Hallazgos estructurales
- Sin métricas de uso para decidir — bloquea: Técnica + Producto / UX + Comercial + Marketing y hype
  - Sin métricas de uso para decidir (Técnica · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Sin métricas de uso para decidir (Producto / UX · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Sin métricas de uso para decidir (Comercial · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Sin métricas de uso para decidir (Marketing y hype · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
- Propuesta de valor poco clara en la portada — bloquea: Producto / UX + Marketing y hype
  - Propuesta de valor poco clara en la portada (Producto / UX · Evidencia: [sintético] el titular no dice qué resuelve)
  - Propuesta de valor poco clara en la portada (Marketing y hype · Evidencia: [sintético] el titular es genérico)

## Matriz impacto × esfuerzo

|  | Esfuerzo BAJO | Esfuerzo MEDIO/ALTO |
|---|---|---|
| **Impacto ALTO** | ⚡ QUICK WINS: Formular una garantía en la página de precios (Comercial)<br>Publicar un testimonio en la portada (Marketing y hype)<br>Añadir pytest con un test de humo (Técnica)<br>Explicar el primer paso en la pantalla inicial (Producto / UX) | 🎯 APUESTAS: Justificar el precio frente a la competencia (Comercial)<br>Reescribir el titular de la portada (Marketing y hype)<br>Documentar el embudo de venta de extremo a extremo (Comercial)<br>Fijar versiones en requirements.txt (Técnica)<br>Reescribir el titular de la portada (Producto / UX)<br>Separar rutas, lógica y acceso a datos (Técnica) |
| **Impacto MEDIO/BAJO** | 📋 Si sobra tiempo: Definir las tres métricas de uso que guían las decisiones (Comercial)<br>Definir las tres métricas de uso que guían las decisiones (Marketing y hype)<br>Definir las tres métricas de uso que guían las decisiones (Técnica)<br>Definir las tres métricas de uso que guían las decisiones (Producto / UX) | 🗑️ Descartar: Unificar el material de venta en un formato (Comercial)<br>Definir la paleta de marca (Marketing y hype)<br>Renombrar las variables de utils.py (Técnica)<br>Unificar el set de iconos (Producto / UX) |

## Roadmap de escalado

Regla de horizonte: impacto × esfuerzo (alto×bajo → H1 · alto×medio → H2 · alto×alto → H3 · medio×bajo → H2). Fuera de las dimensiones prioritarias del objetivo de valor, todo salvo los quick wins baja un horizonte (y lo que cae más allá de H3 no se programa).

### H1 — Esta semana (quick wins)
- [ ] Formular una garantía en la página de precios · sube Comercial
  - Hallazgo: Oferta sin garantía formulada (Comercial · Evidencia: [sintético] la página de precios no menciona garantía)
- [ ] Publicar un testimonio en la portada · sube Marketing y hype
  - Hallazgo: Sin prueba social visible (Marketing y hype · Evidencia: [sintético] ningún testimonio ni caso en la web)
- [ ] Añadir pytest con un test de humo · sube Técnica
  - Hallazgo: Sin tests automatizados (Técnica · Evidencia: [sintético] no existe carpeta tests/)
- [ ] Explicar el primer paso en la pantalla inicial · sube Producto / UX
  - Hallazgo: Onboarding sin estado vacío explicado (Producto / UX · Evidencia: [sintético] la pantalla inicial aparece en blanco)

### H2 — Este mes
- [ ] Justificar el precio frente a la competencia · sube Comercial
  - Hallazgo: Pricing sin justificar frente a la competencia (Comercial · Evidencia: [sintético] un único plan sin comparativa)
- [ ] Reescribir el titular de la portada · sube Producto / UX + Marketing y hype
  - Hallazgo: Propuesta de valor poco clara en la portada (Marketing y hype · Evidencia: [sintético] el titular es genérico)
  - Hallazgo: Propuesta de valor poco clara en la portada (Producto / UX · Evidencia: [sintético] el titular no dice qué resuelve)
- [ ] Definir las tres métricas de uso que guían las decisiones · sube Técnica + Producto / UX + Comercial + Marketing y hype
  - Hallazgo: Sin métricas de uso para decidir (Comercial · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Hallazgo: Sin métricas de uso para decidir (Marketing y hype · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Hallazgo: Sin métricas de uso para decidir (Técnica · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)
  - Hallazgo: Sin métricas de uso para decidir (Producto / UX · Evidencia: [sintético] ninguna decisión del último mes se tomó con datos)

### H3 — Trimestre
- [ ] Documentar el embudo de venta de extremo a extremo · sube Comercial
  - Hallazgo: Rediseñar el proceso de venta de principio a fin (Comercial · Evidencia: [sintético] no hay embudo documentado)
- [ ] Fijar versiones en requirements.txt · sube Técnica
  - Hallazgo: Dependencias sin fijar versión (Técnica · Evidencia: [sintético] requirements.txt sin versiones)

ℹ️ 9 de 9 acciones sin coste estimado · 9 de 9 sin ejecutor asignado: ni los agentes ni el operador los aportaron, y no se inventan.

Apuestas no justificadas por el objetivo de valor (no se programan):
- Monolito sin separación de capas (Técnica · Evidencia: [sintético] app.py concentra rutas, lógica y SQL) · acción propuesta: Separar rutas, lógica y acceso a datos

Descartado por la matriz (impacto medio/bajo con esfuerzo medio/alto; no se programa):
- Material de venta en formatos dispares (Comercial · Evidencia: [sintético] carpeta ventas/ con pdf, ppt y docx) · acción propuesta: Unificar el material de venta en un formato
- Colores de marca no definidos (Marketing y hype · Evidencia: [sintético] cada pieza usa un azul distinto) · acción propuesta: Definir la paleta de marca
- Nombres de variables poco descriptivos (Técnica · Evidencia: [sintético] utils.py usa x, y, tmp) · acción propuesta: Renombrar las variables de utils.py
- Iconografía inconsistente entre pantallas (Producto / UX · Evidencia: [sintético] dos sets de iconos distintos) · acción propuesta: Unificar el set de iconos

## Evolución (solo si hay pasada anterior)
- Primera pasada: este informe es la línea base.

## Datos pendientes que el operador debe aportar
- Volumen mensual de usuarios activos (Técnica, Producto / UX, Comercial, Marketing y hype)
- Dato específico de técnica que solo tiene el operador (Técnica)
- Dato específico de producto / ux que solo tiene el operador (Producto / UX)
- Dato específico de comercial que solo tiene el operador (Comercial)
- Dato específico de marketing y hype que solo tiene el operador (Marketing y hype)

## TOP-5 propuesto para autorización
1. [estructural] Reescribir el titular de la portada (hallazgo: Propuesta de valor poco clara en la portada) · Producto / UX + Marketing y hype · H2
2. [estructural] Definir las tres métricas de uso que guían las decisiones (hallazgo: Sin métricas de uso para decidir) · Técnica + Producto / UX + Comercial + Marketing y hype · H2
3. Formular una garantía en la página de precios (hallazgo: Oferta sin garantía formulada) · Comercial · H1
4. Publicar un testimonio en la portada (hallazgo: Sin prueba social visible) · Marketing y hype · H1
5. Añadir pytest con un test de humo (hallazgo: Sin tests automatizados) · Técnica · H1

> Diagnóstico: nada se ejecuta hasta que el operador autorice el TOP-5.
