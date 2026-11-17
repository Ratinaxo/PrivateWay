# Correcciones de pruebas — 17 de noviembre de 2026

Se conserva el [informe inicial](pilot/REPORT.md) como evidencia de la ejecución del 14 de
noviembre. Esta revisión cambia el protocolo y prueba un candidato de mayor capacidad;
la comparación no permite atribuir las mejoras únicamente al tamaño del modelo.

## Causas y cambios

- **Offsets inválidos:** el modelo ya no calcula posiciones. Extrae valores literales;
  el programa localiza todas sus apariciones exactas en el mensaje indicado. Una cadena
  inventada, un índice inexistente o un juicio normalizado con offsets incorrectos se rechazan.
- **Confusión entre leyes y consultas:** extracción, decisión técnica y fundamento legislativo
  tienen entradas y esquemas separados. El texto legal fundamenta la clasificación; no
  sustituye los criterios técnicos del piloto. El SLM sigue proponiendo la acción y una
  contradicción sigue impidiendo el envío.
- **Omisión de nombres junto a identificadores:** la extracción revisa cada categoría y añade
  una tarea especializada de nombres para los mensajes donde no se encontraron. REGEX se
  conserva localmente; el detector analiza el texto original sin introducir marcadores.
  Todo resultado adicional sigue sujeto al anclaje literal.
- **Errores concurrentes de E5:** la segmentación, los controles de tokens y la codificación
  comparten un bloqueo. Antes, parte del acceso al tokenizador quedaba fuera del bloqueo y
  podía fallar con `RuntimeError: Already borrowed`.
- **Evaluación mezclada con decisiones:** la comparación intrínseca mide extracción sin
  exigir una acción. El flujo completo usa la API ASGI, auditoría y proveedor espía simulado.
- **Resultados acumulados e informes fijos:** cada repetición usa una carpeta independiente.
  Se registran protocolo, modelo, esquemas, dataset, corpus y errores por caso. Los informes
  calculan sus conclusiones desde esos archivos y rechazan configuraciones mezcladas.
  La batería devuelve fallo si las acciones no coinciden o quedan apariciones anotadas visibles.

## Modelo y recursos

El candidato inicial de 3B y sus pesos se conservan. La revisión usa
[Qwen2.5-7B-Instruct-AWQ](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ), con revisión y hashes
registrados en `pilot/models.lock.json`. No se realizó entrenamiento.

Se mantiene vLLM 0.10.2, AWQ-Marlin, contexto 4096, temperatura 0, salida máxima 1024 por llamada
y presupuesto GPU 75 %. El lote de prefill se reduce a 512 para que el modelo quepa en la RTX
3070 de 8 GB sin reducir el contexto. E5 continúa en CPU. El protocolo puede requerir más de
una llamada al SLM por consulta; esto se refleja en la latencia del flujo.

## Resultados de la repetición

La ejecución terminó el 17 de noviembre: **93 pruebas de backend aprobadas** y contratos
del frontend aprobados. Las doce configuraciones del piloto procesaron diez escenarios
de desarrollo cada una sin fallos técnicos. El flujo híbrido acertó las diez acciones con
concurrencias 1, 5 y 10, sin apariciones literales anotadas visibles en los envíos al simulador.

El F2 de coincidencia exacta del híbrido fue 0,923; quedan errores de detección y límites de
cobertura. Esto no demuestra ausencia de PII ni sustituye la validación reservada de 60 casos,
que permanece sin ejecutar. Las latencias y recursos están en el
[informe de la repetición](pilot/REPORT-2026-11-17.md).

## Reproducción

Consultar [README-pilot.md](README-pilot.md) para preparar el modelo y los servicios. Para repetir
la comparación con los mismos diez escenarios:

```powershell
backend/.venv/Scripts/python.exe scripts/run_pilot.py --limite 10 --output-dir pilot/results/nueva-repeticion
backend/.venv/Scripts/python.exe scripts/report_pilot.py --results pilot/results/nueva-repeticion --output pilot/MI-REPORTE.md
```

Usar otra carpeta en cada ejecución. Las evidencias iniciales y las calibraciones intermedias
no se sobreescriben. La validación reservada no se utiliza para ajustar estas correcciones.
