# Preguntas de investigación

## Contexto del estudio

Este trabajo analiza datos meteorológicos horarios obtenidos mediante la API de
Open-Meteo para una celda ERA5 representativa de San Gabriel, cantón Montúfar,
Ecuador.

El período estudiado comprende desde el 1 de enero de 1940 hasta el
31 de diciembre de 2025, con un total de 753 888 registros horarios.

Las variables principales son:

- temperatura del aire a 2 m, en grados Celsius;
- humedad relativa a 2 m, en porcentaje;
- precipitación, en milímetros por hora.

Los datos utilizados corresponden a un producto de reanálisis meteorológico.
Por tanto, no deben interpretarse como mediciones directas de una estación
meteorológica ubicada exactamente en San Gabriel.

---

## Pregunta 1

### ¿Cómo ha evolucionado la temperatura representada por ERA5 para San Gabriel entre 1940 y 2025?

### Motivación

La disponibilidad de una serie histórica de 86 años permite estudiar si existe
una tendencia de largo plazo en la temperatura media y, al mismo tiempo,
observar la variabilidad entre años.

### Estrategia

1. Calcular la temperatura media de cada año.
2. Representar la serie anual entre 1940 y 2025.
3. Ajustar una tendencia lineal descriptiva.
4. Analizar la climatología mensual y horaria.

### Resultado principal observado

La tendencia lineal estimada para la serie completa es aproximadamente:

0.187 °C por década.

Este valor describe la tendencia de la serie ERA5 analizada y no constituye,
por sí mismo, una atribución causal ni una medición instrumental directa del
cambio climático local.

### Figuras relacionadas

- Figura 1: temperatura media anual y tendencia.
- Figura 2: climatología de temperatura por mes y hora.

---

## Pregunta 2

### ¿Hasta qué punto puede predecirse la temperatura futura utilizando su estructura temporal?

### Motivación

La temperatura presenta una elevada autocorrelación. Incluso después de retirar
una tendencia lineal y una climatología mes-hora, los residuos conservan memoria
temporal.

Esto permite estudiar si un modelo autoregresivo puede superar métodos de
predicción simples.

### Estrategia

Se dividió cronológicamente la serie:

- entrenamiento: 1940-2015;
- prueba: 2016-2025.

Se compararon cuatro métodos:

1. persistencia: asumir que la temperatura futura será igual a la actual;
2. misma hora del día anterior;
3. tendencia lineal más climatología;
4. modelo autoregresivo sobre los residuos.

Se evaluaron horizontes de:

1, 3, 6, 12 y 24 horas.

La métrica principal utilizada fue RMSE.

### Resultado principal observado

El modelo autoregresivo obtuvo el menor RMSE en todos los horizontes estudiados.

Por ejemplo:

- horizonte 1 h: RMSE = 0.665 °C;
- horizonte 6 h: RMSE = 1.191 °C;
- horizonte 12 h: RMSE = 1.183 °C;
- horizonte 24 h: RMSE = 1.148 °C.

Esto indica que la serie contiene estructura temporal aprovechable más allá de
la climatología y de los modelos ingenuos de persistencia.

### Figura relacionada

- Figura 3: RMSE según horizonte de predicción y modelo.

---

## Pregunta 3

### ¿Qué tan persistentes son los estados secos y lluviosos, y cuánto aporta la memoria del proceso?

### Motivación

La precipitación presenta una fuerte persistencia temporal.

Debido a que el valor positivo mínimo de precipitación en el dataset es
0.1 mm/h, se definieron dos estados:

- seco: precipitación < 0.1 mm/h;
- lluvia: precipitación >= 0.1 mm/h.

### Estrategia

Se estudiaron tres niveles de complejidad:

1. modelo sin memoria;
2. cadena de Markov de primer orden;
3. modelo cuya probabilidad depende también de la duración del estado actual.

Para la evaluación predictiva se utilizó:

- entrenamiento: 1940-2015;
- prueba: 2016-2025.

Las métricas principales fueron Brier Score y Log Loss.

### Resultados principales observados

Para el modelo de Markov de primer orden se obtuvo aproximadamente:

P(lluvia siguiente | seco) = 0.109

P(lluvia siguiente | lluvia) = 0.890

Esto muestra una fuerte persistencia de los estados meteorológicos.

En el período de prueba:

- modelo sin memoria: Brier = 0.2500;
- Markov orden 1: Brier = 0.0984;
- Markov orden 2: Brier = 0.0979;
- modelo dependiente de duración: Brier = 0.0968.

El modelo dependiente de duración mejora aproximadamente 1.7 % el Brier Score
respecto a Markov de primer orden.

La mejora indica que la duración del episodio contiene información adicional,
aunque la mayor parte de la capacidad predictiva ya es capturada por un modelo
Markoviano sencillo.

### Figuras relacionadas

- Figura 4: matriz de transición seco/lluvia.
- Figura 5: probabilidad de lluvia según duración del estado.

---

## Interpretación general

Los resultados muestran que temperatura y precipitación poseen estructuras
temporales diferentes.

La temperatura puede describirse mediante una combinación de tendencia,
estacionalidad y dependencia autoregresiva.

La ocurrencia de lluvia presenta una fuerte persistencia de estados y puede
aproximarse mediante un modelo de Markov, aunque la duración del episodio
aporta información adicional.

Por tanto, el análisis no requiere asumir desde el inicio un modelo complejo
como una red neuronal. Los modelos estadísticos y estocásticos sencillos
permiten describir y predecir una parte importante de la dinámica observada,
manteniendo además una interpretación clara.
