# Guion de exposición

## Duración objetivo

8 a 10 minutos.

---

# 1. Introducción — 45 segundos

Buenas tardes.

En este trabajo analizamos información climática horaria obtenida de ERA5 para una celda representativa de San Gabriel.

La base cubre el periodo 1940-2025 y contiene 753 888 observaciones horarias.

Trabajamos principalmente con temperatura, humedad relativa y precipitación.

La pregunta central del trabajo fue:

¿Qué patrones temporales existen en estas variables y cuánto de su comportamiento futuro puede explicarse utilizando su historia?

El objetivo no fue simplemente aplicar modelos cada vez más complejos, sino comparar progresivamente cuánto aporta cada nivel adicional de estructura.

---

# 2. Preparación de los datos — 45 segundos

Para evitar fuga de información se utilizó una separación cronológica.

El periodo 1940-2015 se utiliza como entrenamiento.

El periodo 2016-2025 se reserva para evaluación.

Esto es importante porque en series temporales no podemos mezclar aleatoriamente pasado y futuro como suele hacerse en otros problemas de machine learning.

La evaluación predictiva de los modelos AR y SARIMA se realiza a un paso adelante.

Es decir, para predecir una hora utilizamos únicamente la información disponible hasta la hora anterior.

---

# 3. Temperatura: estructura determinista — 1 minuto

La temperatura presenta varios componentes.

Primero tenemos una tendencia de largo plazo.

Además existe una estructura estacional asociada al mes del año y a la hora del día.

Por eso representamos conceptualmente la temperatura como:

temperatura = tendencia + climatología + residuo.

La climatología mes-hora permite capturar, por ejemplo, que una temperatura esperada a las seis de la mañana en enero no es igual a una temperatura esperada a las dos de la tarde en septiembre.

Después de retirar esas componentes obtenemos un residuo.

La pregunta entonces cambia:

¿Ese residuo todavía contiene memoria temporal?

---

# 4. Modelo AR — 1 minuto

Para responder esa pregunta utilizamos primero un modelo autoregresivo.

La idea de un AR es sencilla:

el valor actual depende de valores anteriores de la misma serie.

Aplicado al residuo de temperatura, el modelo AR obtuvo aproximadamente:

MAE = 0.4925 grados Celsius.

RMSE = 0.6653 grados Celsius.

R cuadrado = 0.9527.

Este resultado indica que la historia reciente contiene una cantidad considerable de información predictiva.

Pero todavía nos preguntamos si existe alguna estructura periódica que el AR no capture completamente.

---

# 5. SARIMA — 1 minuto 30 segundos

Para investigar esa posibilidad añadimos un modelo SARIMA.

Utilizamos:

SARIMA (2,0,1) por (1,0,1) con periodo 24.

El número 24 tiene una interpretación directa:

los datos son horarios y 24 observaciones representan un día.

Es importante señalar que SARIMA no se aplica directamente sobre la temperatura cruda.

Antes retiramos la tendencia y la climatología mes-hora.

Por eso los parámetros de diferenciación ordinaria y estacional son cero.

La intención es no volver a eliminar una estructura que ya habíamos tratado explícitamente.

Sobre el periodo de prueba 2016-2025, SARIMA obtuvo:

MAE = 0.4581 grados Celsius.

RMSE = 0.6229 grados Celsius.

R cuadrado = 0.9585.

Frente al AR, esto representa aproximadamente:

6.98 por ciento menos MAE.

6.37 por ciento menos RMSE.

---

# 6. Interpretación AR frente a SARIMA — 45 segundos

Este resultado es importante porque no significa simplemente que SARIMA ganó porque es más complejo.

El modelo AR ya tenía un desempeño muy alto.

Lo que observamos es que una estructura autoregresiva sencilla explica gran parte de la memoria de corto plazo.

SARIMA consigue una mejora adicional porque incorpora explícitamente una dependencia periódica de 24 horas.

Por tanto, todavía existe información temporal residual asociada al ciclo diario.

---

# 7. Precipitación y cadenas de Markov — 1 minuto 30 segundos

Para precipitación utilizamos una estrategia diferente.

En lugar de tratar únicamente la cantidad de lluvia, representamos el sistema mediante dos estados:

seco y lluvia.

Esto permite utilizar cadenas de Markov.

Una cadena de Markov de orden uno pregunta:

si conozco el estado actual, ¿cuál es la probabilidad del siguiente estado?

Por ejemplo:

si ahora está seco, ¿qué probabilidad existe de continuar seco?

Y si ahora llueve, ¿qué probabilidad existe de continuar lloviendo?

Luego estudiamos modelos de orden dos y modelos que incorporan duración.

Con esto podemos preguntar si conocer solamente el estado actual es suficiente o si también importa la historia reciente del episodio.

---

# 8. Conexión matemática — 1 minuto

Aquí aparece la idea que conecta todo el proyecto.

AR, SARIMA y Markov parecen herramientas diferentes, pero estudian el mismo fenómeno:

memoria temporal.

En temperatura tenemos una variable continua.

Para ella utilizamos AR y SARIMA.

En precipitación transformamos el proceso en estados discretos.

Para ellos utilizamos cadenas de Markov.

Por tanto, el proyecto puede resumirse mediante la secuencia:

datos,

patrones,

tendencia y estacionalidad,

dependencia temporal,

memoria,

y finalmente predicción.

---

# 9. Conclusión — 45 segundos

La conclusión principal es que no siempre necesitamos comenzar con el modelo más complejo.

Partimos de estructuras simples y añadimos complejidad únicamente cuando existe evidencia de que aporta información adicional.

En temperatura:

modelo determinista,

luego AR,

y finalmente SARIMA.

En precipitación:

probabilidad global,

Markov de orden uno,

Markov de orden dos,

y duración del episodio.

La idea central del trabajo es:

los patrones describen el comportamiento climático, mientras que la memoria temporal permite convertir esos patrones en información predictiva.

---

# Preguntas probables

## ¿Por qué SARIMA y no ARIMA?

ARIMA permite modelar dependencia temporal no estacional.

SARIMA extiende esa estructura incorporando además una componente estacional explícita.

Como nuestros datos son horarios, queríamos comprobar si permanecía una dependencia asociada al ciclo de 24 horas.

## ¿Por qué no reemplazar simplemente AR por SARIMA?

Porque AR funciona como modelo de referencia más simple.

Compararlos nos permite medir cuánto aporta realmente la complejidad adicional de SARIMA.

## ¿Por qué d = 0 y D = 0?

Porque previamente retiramos tendencia y climatología mes-hora.

Aplicar diferenciación adicional podría eliminar estructura que ya había sido tratada explícitamente.

## ¿Qué significa R cuadrado igual a 0.9585?

Significa que, bajo esta evaluación y para este conjunto de prueba, las predicciones de SARIMA reproducen una proporción muy alta de la variabilidad observada.

No significa que podamos pronosticar libremente diez años hacia el futuro con esa precisión.

## ¿Se pronosticaron diez años completos desde 2016?

No.

La evaluación es de un paso adelante.

Cada predicción horaria utiliza la historia observada disponible hasta el instante anterior.

## ¿Por qué usar Markov para lluvia?

Porque podemos representar la ocurrencia de precipitación mediante estados discretos como seco y lluvia.

Markov permite estudiar directamente las probabilidades de transición entre esos estados.

## ¿Cuál es la relación entre Markov y SARIMA?

Ambos estudian dependencia temporal.

SARIMA lo hace sobre una variable continua.

Markov lo hace sobre estados discretos.

## ¿Por qué utilizar cinco años para estimar SARIMA?

El conjunto horario completo contiene cientos de miles de observaciones.

Se utilizó una ventana reciente de cinco años para mantener el ajuste computacionalmente manejable y representar adecuadamente la dinámica reciente disponible antes del periodo de prueba.

Esta es una decisión metodológica que debe interpretarse como parte del diseño del benchmark y no como una afirmación de que cinco años sean universalmente óptimos.

## ¿Entonces SARIMA es el mejor modelo?

En esta comparación concreta, SARIMA obtiene los menores errores entre los modelos considerados para la predicción horaria de temperatura.

Sin embargo, el objetivo del trabajo es comparar cuánto aporta cada nivel de complejidad, no afirmar que SARIMA sea universalmente superior.

## ¿Qué podría hacerse después?

Se podrían estudiar diferentes órdenes SARIMA mediante validación temporal, comparar otros horizontes de pronóstico, incorporar variables exógenas y evaluar modelos adicionales sobre exactamente las mismas ventanas temporales.
