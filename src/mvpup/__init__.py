"""MVP-UP — orquestador de auditoría de producto en 10 dimensiones.

El núcleo es determinista y no hace red: selección de dimensiones, prompts,
validación del formato de los agentes, puntuación ponderada, matriz, roadmap,
comparación entre pasadas e informe. Los agentes se enchufan vía `runners`.
"""

__version__ = "0.1.0"
