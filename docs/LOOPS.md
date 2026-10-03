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
