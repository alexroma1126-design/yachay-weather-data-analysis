from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

README = ROOT / "README.md"
METRICS = ROOT / "data" / "analysis" / "sarima_temperature_metrics.csv"

START = "<!-- EXPOSICION_START -->"
END = "<!-- EXPOSICION_END -->"

df = pd.read_csv(METRICS)

def model(name):
    row = df.loc[df["model"] == name]
    if row.empty:
        raise ValueError(f"No se encontró el modelo {name}")
    return row.iloc[0]

persistence = model("persistence")
deterministic = model("deterministic")
sarima = model("sarima")

# Resultados del AR de horizonte 1 obtenidos previamente.
ar_mae = 0.4925
ar_rmse = 0.6653
ar_r2 = 0.9527

mae_gain = 100 * (ar_mae - sarima["mae"]) / ar_mae
rmse_gain = 100 * (ar_rmse - sarima["rmse"]) / ar_rmse

section = rf"""
{START}

# Guion para la exposición

## 1. Pregunta central

Este proyecto analiza una serie climática horaria ERA5 para una celda
representativa de San Gabriel durante **1940-2025**.

Se dispone de **753 888 observaciones horarias**.

Las variables principales son:

- temperatura a 2 metros;
- humedad relativa;
- precipitación.

La pregunta central es:

> ¿Qué patrones y qué memoria temporal existen en las variables
> climáticas y cuánto ayudan a predecir su comportamiento futuro?

---

## 2. División temporal

La evaluación respeta estrictamente el orden temporal:

- **Entrenamiento:** 1940-2015.
- **Prueba:** 2016-2025.

Así se evita utilizar información futura durante el entrenamiento.

La evaluación predictiva de AR y SARIMA se realiza a **un paso adelante**:
para predecir cada hora se permite utilizar la historia observada hasta la
hora inmediatamente anterior. Por tanto, los resultados representan
predicción horaria condicionada a información pasada disponible y no un
pronóstico recursivo libre de diez años.

---

## 3. Temperatura

La temperatura se estudia mediante la idea:

```text
TEMPERATURA
    |
    +--- tendencia
    |
    +--- climatología mes-hora
    |
    +--- residuo
            |
            +--- dependencia temporal
```

Primero se retiran la tendencia y la climatología mes-hora.

Después se modela la memoria que permanece en los residuos.

Los modelos se comparan progresivamente:

```text
Persistencia
     |
     v
Determinista
     |
     v
AR
     |
     v
SARIMA
```

---

## 4. Modelo SARIMA

El nuevo modelo es:

```text
SARIMA(2,0,1) x (1,0,1,24)
```

El periodo estacional **24** representa el ciclo diario de una
serie horaria.

SARIMA se aplica sobre los residuos después de retirar previamente
la tendencia y la climatología mes-hora.

Por eso utilizamos:

```text
d = 0
D = 0
```

La pregunta es si todavía queda una dependencia periódica que el
modelo AR no capture completamente.

---

## 5. Resultados

Evaluación sobre el periodo **2016-2025**:

| Modelo | MAE | RMSE | R² |
|---|---:|---:|---:|
| Persistencia | {persistence["mae"]:.4f} | {persistence["rmse"]:.4f} | {persistence["r2"]:.4f} |
| Determinista | {deterministic["mae"]:.4f} | {deterministic["rmse"]:.4f} | {deterministic["r2"]:.4f} |
| AR | {ar_mae:.4f} | {ar_rmse:.4f} | {ar_r2:.4f} |
| **SARIMA** | **{sarima["mae"]:.4f}** | **{sarima["rmse"]:.4f}** | **{sarima["r2"]:.4f}** |

Para SARIMA:

```text
MAE  = {sarima["mae"]:.4f} °C
RMSE = {sarima["rmse"]:.4f} °C
R²   = {sarima["r2"]:.4f}
```

Frente al AR:

```text
reducción MAE  = {mae_gain:.2f} %
reducción RMSE = {rmse_gain:.2f} %
```

El AR ya explica una gran parte de la dependencia temporal.

SARIMA consigue una mejora adicional al representar explícitamente
estructura periódica residual asociada al ciclo de 24 horas.

Por tanto:

> **La mayor parte de la memoria de corto plazo puede modelarse con AR,
> pero existe información temporal adicional que SARIMA puede aprovechar.**

---

## 6. Precipitación

La precipitación se estudia como un sistema discreto:

```text
SECO <------> LLUVIA
```

La complejidad aumenta progresivamente:

```text
Probabilidad global
        |
        v
Markov orden 1
        |
        v
Markov orden 2
        |
        v
Duración del episodio
```

La pregunta es si la probabilidad futura de lluvia depende únicamente
del estado actual o también de la historia reciente.

---

## 7. La conexión entre SARIMA y Markov

Aunque los modelos son diferentes, todos estudian **memoria temporal**:

```text
                 MEMORIA TEMPORAL
                       |
            +----------+----------+
            |                     |
            v                     v
       TEMPERATURA           PRECIPITACIÓN
            |                     |
            v                     v
    variable continua       estados discretos
            |                     |
            v                     v
       AR / SARIMA              MARKOV
```

AR y SARIMA modelan dependencia temporal sobre una variable continua.

Markov modela dependencia temporal sobre estados discretos.

---

## 8. Idea central del trabajo

```text
DATOS
  |
  v
PATRONES
  |
  v
TENDENCIA Y ESTACIONALIDAD
  |
  v
DEPENDENCIA TEMPORAL
  |
  v
MEMORIA
  |
  v
PREDICCIÓN
```

El objetivo no fue escoger automáticamente el modelo más complejo.

La estrategia fue aumentar progresivamente la complejidad y comprobar
si cada nuevo componente aporta información predictiva.

---

## 9. Mensaje final para la exposición

Para temperatura:

```text
Determinista -> AR -> SARIMA
```

Para precipitación:

```text
Probabilidad -> Markov 1 -> Markov 2 -> Duración
```

La idea que conecta todo el proyecto es:

> **Los patrones describen el comportamiento climático; la memoria
> temporal permite convertir esos patrones en información predictiva.**

---

## 10. Reproducción desde VS Code

Desde la raíz del proyecto:

```powershell
.\\.venv\\Scripts\\python.exe src\compare_models.py
.\\.venv\\Scripts\\python.exe src\horizon_duration_diagnostics.py
.\\.venv\\Scripts\\python.exe src\compare_rain_state_models.py
.\\.venv\\Scripts\\python.exe src\compare_sarima.py
.\\.venv\\Scripts\\python.exe src\generate_figures.py
```

{END}
""".strip()

current = README.read_text(encoding="utf-8")

if START in current and END in current:
    before = current.split(START, 1)[0].rstrip()
    after = current.split(END, 1)[1].lstrip()

    updated = before + "\n\n" + section + "\n"

    if after:
        updated += "\n" + after
else:
    updated = current.rstrip() + "\n\n" + section + "\n"

README.write_text(updated, encoding="utf-8")

print()
print("=" * 60)
print("README ACTUALIZADO")
print("=" * 60)
print(f"SARIMA MAE:       {sarima['mae']:.4f}")
print(f"SARIMA RMSE:      {sarima['rmse']:.4f}")
print(f"SARIMA R2:        {sarima['r2']:.4f}")
print(f"Mejora MAE vs AR: {mae_gain:.2f}%")
print(f"Mejora RMSE:      {rmse_gain:.2f}%")



