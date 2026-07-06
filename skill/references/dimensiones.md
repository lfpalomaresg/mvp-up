# MVP-UP — Las 10 dimensiones y sus agentes

## Plantilla común de prompt (todas las dimensiones)

Cada agente se lanza con el tipo `general-purpose` (o `Explore` si solo lee código) y este prompt base
+ el bloque de su dimensión:

```
Eres el agente de la dimensión [DIMENSIÓN] de una auditoría MVP-UP.
Producto: [NOMBRE] · Etapa: [ETAPA] · Objetivo de valor: [OBJETIVO]
Ruta local: [RUTA] · URL desplegada: [URL o "no desplegado"]
Contexto de negocio: [resumen de AI_OS/PROJECTS/<producto>.md]

REGLAS: Solo análisis. NO modifiques archivos, NO hagas commits, NO llames APIs de pago.
Evalúa únicamente lo verificable; lo que no puedas verificar, márcalo como N/D.

Evalúa lo que indica tu bloque de dimensión y devuelve EXACTAMENTE este formato:

## Score: X/10 (rúbrica al pie)
## Hallazgos (máx 7, ordenados por impacto)
- [H1] <hallazgo> · Impacto: A/M/B · Esfuerzo: A/M/B · Evidencia: <archivo/dato concreto>
## Quick wins (impacto A/M con esfuerzo B)
## Riesgos si no se actúa
## Datos que faltan para evaluar mejor
```

**Rúbrica común 0-10:** 0-2 crítico o inexistente · 3-4 deficiente, bloquea el escalado ·
5-6 funcional con huecos claros · 7-8 sólido, mejoras incrementales · 9-10 listo para escalar.

---

## 1 · Técnica (código, arquitectura, front/back, deuda)

- **Evalúa:** calidad y estructura del código, arquitectura front/back, deuda técnica, tests, dependencias desactualizadas/vulnerables, capacidad de crecer (¿aguanta 10× usuarios/clientes?), documentación técnica, facilidad de traspaso a otro desarrollador.
- **Fuentes:** repo local (leerlo), `package.json`/lockfiles, estructura de carpetas, README, CI si existe. Si es web: criterios de `tool-quality-gate`.
- **N/A si:** el producto no tiene software.

## 2 · Seguridad

- **Evalúa:** credenciales expuestas, endpoints sin proteger, auth/authz, validación de inputs, rate limiting, headers, RLS/permisos de BBDD, gestión de secretos, dependencias con CVEs.
- **Fuentes:** repo + URL desplegada. Criterios de `tool-seguridad-ia` (10 riesgos críticos) y rama seguridad de `tool-site-audit`.
- **N/A si:** no hay software ni datos de clientes. Si hay datos de clientes aunque no haya app (p.ej. hojas de cálculo de un servicio), evaluar la variante "servicio": dónde viven los datos, quién accede, copias.

## 3 · Legal

- **Evalúa:** RGPD (base jurídica, política privacidad, encargados de tratamiento), LSSI-CE/aviso legal, cookies (criterio AEPD), términos de servicio, propiedad intelectual y marca (¿registrada? ¿OEPM?), contratos con clientes/proveedores, licencias de dependencias y assets.
- **Fuentes:** URL desplegada (textos legales), repo (licencias), contexto de negocio. Rama legal de `tool-site-audit`.
- **Variante servicio:** contratos, hojas de encargo, seguros de responsabilidad, normativa sectorial aplicable.

## 4 · Producto / UX

- **Evalúa:** claridad de la propuesta de valor en 5 segundos, fricción del onboarding, flujo principal (¿cuántos pasos hasta el valor?), estados vacíos/de error, accesibilidad básica, móvil, coherencia visual, ¿qué le sobra? (feature creep).
- **Fuentes:** usar el producto de verdad (URL o app local), capturas, README de usuario.

## 5 · Comercial (oferta, pricing, canales)

- **Evalúa:** oferta formulada (¿Grand Slam Offer estilo Hormozi?: resultado soñado × probabilidad ÷ tiempo × esfuerzo), pricing definido y justificado, garantías, objeciones mapeadas, canales de venta activos, proceso de venta repetible, ¿quién vende si no vende el operador?
- **Fuentes:** web/materiales de venta, ficha AI_OS del producto, ejercicio Capa 3 si existe (`project_blindbeds_capa3_oferta`).

## 6 · Marketing y hype (posicionamiento, ICP, contenido, proyección)

- **Evalúa:** posicionamiento diferenciado (¿por qué tú y no el de al lado?), ICP definido, presencia y contenido (¿hay motor de contenido o silencio?), prueba social (testimonios, casos), narrativa/hype honesto (demo grabable, historia contable), SEO básico.
- **Fuentes:** web, LinkedIn/redes del producto, outputs de `marketing-positioning`/`marketing-icp` si existen (leerlos, no relanzar).

## 7 · Mercado (nicho, competencia, oportunidades)

- **Evalúa:** tamaño y accesibilidad del nicho, 3-5 competidores directos con precios, hueco real, tendencias del sector, riesgo de plataforma o regulatorio, oportunidades adyacentes (¿a quién más le sirve esto sin reconstruirlo?).
- **Fuentes:** búsqueda web (patrón de `strategy-research` modo quick: 3-5 fuentes citadas). Este agente SÍ navega.

## 8 · Económica (costes, ingresos, unit economics)

- **Evalúa:** coste de desarrollo hundido (informativo), costes recurrentes (hosting, APIs, dominios, licencias — buscarlos de verdad en el repo/config), coste por cliente adicional, precio vs coste (margen unitario), break-even (¿cuántos clientes cubren los fijos?), ingresos actuales si los hay.
- **Regla dura:** NO inventar cifras. Todo importe sin fuente = N/D + pedir el dato.
- **Fuentes:** configs del repo (qué servicios usa), ficha AI_OS, datos que aporte el operador.

## 9 · Operativa (procesos, dependencia del operador, soporte)

- **Evalúa:** qué pasos dependen manualmente del operador (mapa honesto), ¿qué pasa si el operador desaparece 2 semanas?, onboarding de un cliente nuevo (pasos, horas), soporte (¿canal definido?), procesos documentados vs en la cabeza, automatizable con loops (`automation-loop-engine`).
- **Fuentes:** ficha AI_OS, workflows documentados, entrevista corta al operador si hace falta.

## 10 · Datos y medición (analítica, métricas, feedback)

- **Evalúa:** ¿hay analítica instalada? (web/producto), ¿se miden las 3-5 métricas que importan para el objetivo de valor?, ¿hay canal de feedback de usuarios?, ¿las decisiones del último mes se tomaron con datos o a ojo?, ¿qué dato barato de instalar cambiaría la próxima decisión?
- **Nota:** esta dimensión alimenta a todas las demás en la re-auditoría — sin medición, los Δ de score son opinión.
- **Fuentes:** repo (¿hay tracking?), herramientas conectadas, ficha AI_OS.

---

## Agrupación en modo express

Cuando express selecciona 3-5 dimensiones, se pueden agrupar 2 dimensiones afines en un mismo agente
para ahorrar coste: técnica+seguridad · comercial+marketing · mercado+económica · legal+operativa.
Nunca agrupar más de 2 en un agente (baja la calidad del análisis).

---

## Modo ligera (semillas, utilidades, proyectos congelados)

Un solo agente (Sonnet) con este prompt — sin agentes por dimensión, sin matriz completa:

```
Eres el agente único de una pasada LIGERA MVP-UP (diagnóstico de semilla, no auditoría completa).
Proyecto: [NOMBRE]. Lee primero su ficha AI_OS ([RUTA FICHA]) y después el repo [RUTA]
(README, docs, estructura, git log --oneline -10).
Contexto del operador: [foco estratégico + carriles WIP activos].
REGLAS: solo análisis; nada se modifica/instala/arranca. Cifras sin fuente = N/D. Máx ~40 líneas.

Devuelve EXACTAMENTE:
## Score orientativo: X/10
## Qué es y estado real (3-4 líneas: qué hay construido DE VERDAD vs lo que dice la ficha)
## Hallazgos clave (3-5, con evidencia) - [H1] ... · Impacto: A/M/B
## Valor potencial (1-2 líneas: a qué objetivo del operador sirve — o si conviene archivarla)
## 3 tareas de reanudación (lo primero al retomar, concretas y ordenadas — o de CIERRE si recomienda archivar)
```

El informe ligera se guarda igual en `_escalado/<proyecto>/` y lleva el mismo anclaje "salta al retomar".
Señal para elegir ligera: proyecto fuera de carriles WIP, sin actividad reciente en git, o utilidad interna.
