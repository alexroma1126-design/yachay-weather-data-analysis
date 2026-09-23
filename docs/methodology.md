# Metodología

## 1. Objetivo

El proyecto utiliza datos meteorológicos obtenidos mediante la API histórica de
Open-Meteo para estudiar patrones temporales de temperatura y precipitación en
una celda ERA5 representativa de San Gabriel, cantón Montúfar, Ecuador.

La metodología fue diseñada para que todo el análisis sea reproducible desde
los datos originales hasta las figuras finales.

---

## 2. Fuente de datos

Fuente:

- Open-Meteo Historical Weather API
- Modelo seleccionado explícitamente: ERA5

Ubicación solicitada:

- latitud: 0.59354
- longitud: -77.83066
- zona horaria: America/Guayaquil

La API devolvió de forma consistente la siguiente celda:

- latitud de la celda: 0.5
- longitud de la celda: -77.75
- elevación reportada: 2856 m

Los datos corresponden a un producto meteorológico de reanálisis y no a
mediciones directas de una estación instalada exactamente en San Gabriel.

---

## 3. Período analizado

Se utilizaron datos desde:

1940-01-01 00:00

hasta:

2025-12-31 23:00

Esto corresponde a:

- 86 años;
- 753 888 observaciones horarias.

---

## 4. Variables

Las variables principales fueron:

- `temperature_2m`: temperatura del aire a 2 m, en °C;
- `relative_humidity_2m`: humedad relativa a 2 m, en %;
- `precipitation`: precipitación horaria, en mm.

También se conservó el timestamp correspondiente a cada observación.

---

## 5. Adquisición de datos

La adquisición fue realizada mediante:

`src/audit_archive.py`

Los datos se descargaron por año para facilitar:

- recuperación ante interrupciones;
- auditoría individual;
- reutilización de archivos previamente descargados;
- identificación de problemas específicos por año.

Los archivos originales fueron almacenados localmente en:

`data/raw/`

Estos archivos no se incluyen en Git porque pueden regenerarse mediante el
script de adquisición.

---

## 6. Auditoría de calidad

Cada año fue sometido a comprobaciones automáticas.

Se verificó:

1. número esperado de registros;
2. continuidad horaria;
3. ausencia de timestamps duplicados;
4. ausencia de valores faltantes;
5. longitudes consistentes entre variables;
6. humedad relativa dentro del intervalo 0-100 %;
7. precipitación no negativa;
8. unidades consistentes;
9. zona horaria consistente;
10. coordenadas y metadatos consistentes entre años.

Los 86 años superaron la auditoría.

No se encontraron inconsistencias de metadatos dentro de la serie utilizada.

---

## 7. Dataset maestro

Los 86 archivos anuales fueron integrados mediante:

`src/build_master_dataset.py`

El resultado fue:

`data/processed/era5_master_1940_2025.csv`

El archivo contiene:

- 753 888 filas de datos;
- una fila adicional de encabezados;
- 4 columnas originales.

Columnas:

- timestamp;
- temperature_2m;
- relative_humidity_2m;
- precipitation.

El dataset maestro fue validado nuevamente después de la integración.

Su huella SHA-256 fue:

`8e46e53cd1d47057cd65f86ef9bc7a256a9192a308cf2f5ff506ac34c3a30cc8`

---

## 8. Análisis exploratorio

El análisis exploratorio fue implementado en:

`src/profile_dataset.py`

Se calcularon:

- estadísticas globales;
- percentiles;
- promedios anuales;
- promedios mensuales;
- resúmenes por década;
- precipitación anual;
- correlaciones;
- autocorrelaciones temporales.

Entre los resultados preliminares se observó:

- temperatura media global aproximada: 11.298 °C;
- temperatura mínima horaria: 1.2 °C;
- temperatura máxima horaria: 22.9 °C;
- humedad relativa media: 85.812 %.

---

## 9. Diagnóstico temporal de temperatura

La temperatura fue representada conceptualmente como:

T_t = m(t) + X_t

donde:

- `m(t)` representa tendencia y estructura estacional;
- `X_t` representa el residuo temporal.

Se estimó:

1. una tendencia lineal;
2. una climatología mes-hora;
3. autocorrelaciones de la serie original;
4. autocorrelaciones de los residuos.

Incluso después de retirar tendencia y climatología, los residuos conservaron
dependencia temporal.

Por ejemplo:

- autocorrelación residual a 1 h: aproximadamente 0.828;
- autocorrelación residual a 24 h: aproximadamente 0.522.

Esto justificó estudiar un modelo autoregresivo.

---

## 10. Separación entrenamiento-prueba

Para evitar utilizar información futura durante la evaluación predictiva, se
realizó una división cronológica.

Entrenamiento:

1940-01-01 a 2015-12-31

Prueba:

2016-01-01 a 2025-12-31

Las componentes utilizadas por los modelos predictivos fueron estimadas
únicamente con información del período de entrenamiento cuando correspondía.

No se realizó una división aleatoria de los registros porque se trata de una
serie temporal.

---

## 11. Modelos de temperatura

Se compararon cuatro estrategias:

### Persistencia

La temperatura futura se estima como la temperatura observada en el instante
actual.

### Modelo diario ingenuo

La temperatura futura se estima utilizando la observación correspondiente a la
misma hora del día anterior.

### Modelo determinista

Combina:

- tendencia temporal;
- climatología mes-hora.

### Modelo autoregresivo

Añade información proveniente de residuos observados en retardos temporales.

Se estudiaron horizontes de:

- 1 h;
- 3 h;
- 6 h;
- 12 h;
- 24 h.

Las métricas utilizadas fueron:

- MAE;
- RMSE;
- R².

El modelo autoregresivo presentó el menor RMSE en todos los horizontes
analizados.

---

## 12. Modelado estocástico de la lluvia

El valor positivo mínimo de precipitación observado en el dataset fue:

0.1 mm/h

Por esta razón se definieron los estados:

- 0: seco, precipitación < 0.1 mm/h;
- 1: lluvia, precipitación >= 0.1 mm/h.

Se estudiaron:

1. modelo sin memoria;
2. cadena de Markov de primer orden;
3. cadena de Markov de segundo orden;
4. modelo dependiente de la duración del estado.

Para Markov de primer orden se estimaron aproximadamente:

P(lluvia siguiente | seco) = 0.109

P(lluvia siguiente | lluvia) = 0.890

Esto muestra una fuerte persistencia temporal.

---

## 13. Dependencia de la duración

Se analizaron las duraciones consecutivas de los estados seco y lluvioso.

Una cadena de Markov de primer orden supone que la probabilidad de continuar en
un estado depende únicamente del estado actual.

Los datos mostraron pequeñas variaciones asociadas con la duración del episodio.

Se construyó por ello un modelo adicional basado en:

P(R_(t+1) | R_t, D_t)

donde `D_t` representa la duración acumulada del estado actual.

En el conjunto de prueba:

- Markov orden 1: Brier ≈ 0.0984;
- Markov orden 2: Brier ≈ 0.0979;
- modelo dependiente de duración: Brier ≈ 0.0968.

La mejora relativa del modelo dependiente de duración respecto a Markov de
primer orden fue aproximadamente 1.7 %.

Esto indica que la duración contiene información adicional, aunque la mayor
parte de la predictibilidad ya es capturada por el modelo de primer orden.

---

## 14. Métricas

### Temperatura

Se utilizaron:

- MAE;
- RMSE;
- R².

El RMSE fue utilizado como métrica principal para comparar los modelos de
temperatura.

### Lluvia

Se utilizaron:

- Brier Score;
- Log Loss;
- Accuracy.

Para modelos probabilísticos, Brier Score y Log Loss fueron considerados más
informativos que Accuracy por sí sola.

---

## 15. Visualizaciones

Las cinco figuras finales fueron generadas mediante Matplotlib desde:

`src/generate_figures.py`

Las figuras son:

1. temperatura media anual y tendencia lineal;
2. climatología de temperatura por mes y hora;
3. RMSE según horizonte de predicción;
4. matriz de transición seco-lluvia;
5. probabilidad de lluvia siguiente según duración del estado.

Todas las figuras se almacenan en:

`figures/`

---

## 16. Reproducibilidad

La secuencia principal del proyecto es:

Open-Meteo API
→ archivos ERA5 anuales
→ auditoría
→ dataset maestro
→ análisis exploratorio
→ diagnóstico temporal
→ modelos predictivos
→ figuras finales

Los principales scripts son:

- `src/audit_archive.py`
- `src/build_master_dataset.py`
- `src/profile_dataset.py`
- `src/stochastic_diagnostics.py`
- `src/compare_models.py`
- `src/horizon_duration_diagnostics.py`
- `src/compare_rain_state_models.py`
- `src/generate_figures.py`

---

## 17. Limitaciones

Los resultados deben interpretarse considerando las siguientes limitaciones.

1. ERA5 es un producto de reanálisis y no una estación meteorológica local.
2. El análisis corresponde a una celda representativa del área de San Gabriel.
3. Una tendencia estadística observada no implica por sí sola causalidad.
4. Los modelos predictivos fueron evaluados únicamente dentro del período
   2016-2025.
5. Los resultados dependen de las variables y resoluciones disponibles en el
   conjunto utilizado.
6. El modelo de lluvia simplifica la precipitación a estados binarios para una
   parte del análisis.
7. Los modelos evaluados son deliberadamente interpretables y relativamente
   sencillos; no se buscó maximizar la complejidad algorítmica.

---

## 18. Criterio metodológico

El proyecto prioriza:

- reproducibilidad;
- validación temporal;
- interpretabilidad;
- comparación contra modelos simples;
- complejidad justificada por evidencia.

Por esta razón no se incorporó una red neuronal únicamente por aumentar la
complejidad. Los modelos autoregresivos y estocásticos ya permiten describir
una parte importante de la estructura presente en los datos.
