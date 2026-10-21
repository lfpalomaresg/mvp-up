# Ejemplos

`informe-ejemplo-dry-run.md` / `.json` — salida REAL del modo seco
(`mvpup run ... --dry-run`) con el producto ficticio «Ejemplo SaaS de reservas»:

- Agentes simulados: ni una llamada a la API, ni una lectura de repo real.
- Cada evidencia va marcada `[sintético]` y el informe lleva aviso de cabecera.
- Sirve para ver el formato del informe (scores, matriz impacto×esfuerzo, TOP-5,
  JSON gemelo) sin gastar dinero y sin datos de ningún cliente.
- No cuenta como pasada del ciclo: un dry-run nunca se compara con el histórico.

Para regenerarlo:

```bash
mvpup run --product "Ejemplo SaaS de reservas" --stage mvp --objective ingresos \\
  --dry-run --out ./examples
```
