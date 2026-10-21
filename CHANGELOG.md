# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) · versionado semántico.

## [0.2.0] — 2026-10-21

Versión de presentación pública: mismo núcleo, más fácil de evaluar y de integrar.

### Añadido
- `mvpup --version` (lee `mvpup.__version__`; test que comprueba que no desincroniza con\n  el metadato del paquete).
- `examples/`: informe seco REAL (`--dry-run`) con producto ficticio, en Markdown y
  JSON, con su propio README — el formato del informe se ve sin gastar un céntimo.
- `README.en.md` (inglés) y este CHANGELOG.
- `ruff` como red mínima de lint (E, F, W, I, B; `E501` fuera por estilo) en
  `[tool.ruff]` y en el workflow de CI.
- Test de `--version` sin subcomando.

### Cambiado
- CI: `ruff check src tests` antes de mypy y pytest.

### Notas
- Sin cambios de comportamiento en la lógica de auditoría.
- Pendiente para cuando el operador autorice push: tag `v0.2.0` y notas de release.
