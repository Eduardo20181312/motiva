# 1. Qué es MOTIVA y qué cambió

## 1.1 El sistema en una página

MOTIVA es un sistema de monitoreo de ocupación. Una cámara mira la entrada de un espacio; el programa detecta a las personas, las sigue de una imagen a la siguiente y cuenta una **entrada** o una **salida** según el sentido en que cruzan dos líneas dibujadas sobre la imagen. Con esos dos contadores calcula la **ocupación** (entradas menos salidas, nunca menor que cero) y la compara con el **aforo máximo** que definió el usuario.

Componentes:

| Componente | Qué es |
|---|---|
| Equipo | Raspberry Pi 4 Model B (4 GB), sin acelerador gráfico; todo corre en la CPU |
| Cámara | Cámara web USB, usada a 640x480 |
| Detector | YOLO11s de una sola clase (`person`), entrenado por el autor, ejecutado con OpenVINO |
| Seguimiento | ByteTrack, con parámetros ajustados para pocas detecciones por segundo |
| Programa | `motiva_app.py`, un solo archivo en Python |
| Interfaz | Menú de configuración (CustomTkinter, sobre Tkinter), ventana de monitoreo (OpenCV), informe de sesión, página web para celular, LED de alerta |
| Salidas | Registro CSV por sesión, informe PNG con gráfica, estado en vivo por la red local |

El programa también puede analizar un archivo de video en lugar de la cámara, con la misma lógica de conteo. Ese modo se usó para todas las pruebas repetibles.

## 1.2 Flujo de uso

1. El usuario abre MOTIVA desde un ícono en el escritorio de la Raspberry. Mientras revisa el menú, el modelo de detección se prepara en segundo plano.
2. En el menú escribe el nombre del espacio y el aforo máximo, y elige la fuente (cámara o video), la orientación de las líneas, el sentido de entrada y la calidad de detección. El menú recuerda lo elegido la vez anterior.
3. Pulsa INICIAR. Se abre la ventana de monitoreo con el video, las líneas, las cajas de las personas y los contadores.
4. Puede arrastrar las líneas con el mouse, pausar con ESPACIO y terminar con Q.
5. Mientras tanto, cualquier celular en la misma red wifi puede ver los contadores en una página web, y un LED parpadea si se supera el aforo.
6. Al terminar, se muestra un informe con las cifras de la sesión y una gráfica de la ocupación en el tiempo. El informe (PNG) y el registro de cada conteo (CSV) quedan guardados en la carpeta `registros/`.

## 1.3 Estado antes de estas sesiones

Antes del 10 de octubre de 2026, `motiva_app.py` (escrito por el autor) ya tenía:

- Menú Tkinter con nombre del espacio, aforo máximo, fuente (cámara o video) e intervalo de inferencia (1 a 10).
- Modelo `best.onnx` (YOLO11s a 640x640) ejecutado con ONNX Runtime, llamando a `model.track` cada `INTERVAL` frames y reutilizando el último resultado en los frames intermedios.
- Dos líneas horizontales, verde a 1/3 del alto y roja a 2/3, arrastrables con el mouse.
- Conteo por zonas (`arriba`, `medio`, `abajo`) según el centro de la caja de cada persona.
- Dibujo sobre el video: encabezado con cronómetro, panel inferior con entradas, salidas, ocupación, aforo y barra de nivel, y aviso "AFORO SUPERADO".
- Registro CSV con hora, entradas, salidas y ocupación, y un cuadro de resumen al terminar.

Las versiones aún más antiguas están en `codigo/versiones_anteriores/`.

## 1.4 Todo lo que cambió, en orden

### 10 de octubre de 2026, primera sesión: correcciones

| Cambio | Detalle |
|---|---|
| Pausa | Antes, reanudar con ESPACIO casi nunca funcionaba. Ahora reanuda siempre, se ve el aviso de pausa y se pueden mover las líneas con el video detenido |
| Hilo eliminado | El video corría en un hilo secundario que no aportaba nada y era inseguro para OpenCV y los cuadros de mensaje. Ahora el bucle principal corre en el hilo principal |
| Error de fuente | Si la cámara o el video abren pero no entregan imagen, sale un mensaje en vez de caerse |
| CSV al instante | Cada conteo se escribe a disco de inmediato (`flush`), para no perder datos si el programa se cierra mal |
| Reasignación de IDs | Si el seguidor pierde a una persona y le da un ID nuevo, el ID nuevo hereda la zona del ID perdido más cercano, para no perder ese cruce |
| Líneas verticales | Nueva opción en el menú: líneas horizontales o verticales, con la misma lógica de conteo |

### 10 de octubre de 2026, segunda sesión: rendimiento en vivo y en video

| Cambio | Detalle |
|---|---|
| Lectura y detección en hilos aparte | Clases `LectorCamara`, `LectorVideo` y `Detector`. El video ya no se congela mientras el modelo trabaja |
| Tamaño de entrada por fuente | Cámara a 320 y video a 640 (`IMGSZ_CAMARA`, `IMGSZ_VIDEO`), con `rect=True` para no rellenar la imagen |
| Modelo de entrada variable | `modelos/best_dinamico.onnx`, exportado desde los pesos de junio recuperados (ver `06_entorno_e_instalacion.md`) |
| Seguidor ByteTrack ajustado | `modelos/tracker_motiva.yaml`. El seguidor por defecto perdía a las personas cuando había pocas detecciones por segundo |
| Cajas adelantadas | La caja se dibuja donde la persona debería ir, según su velocidad, porque cada detección llega con retraso (`ADELANTO_MAX`) |
| Video parejo | En modo video los frames salen a intervalos iguales, y los videos de más de 960 px se achican al leerlos (`LADO_MAX_VIDEO`) |

### 12 de octubre de 2026: motor, filtros, interfaz y salidas

| Cambio | Detalle |
|---|---|
| OpenVINO | El modelo pasó de ONNX Runtime a OpenVINO. Mismas detecciones, entre 20 y 45 % más rápido |
| Etiqueta `PERSON ID n` | Cada caja muestra la clase y el identificador |
| Filtro de objetos quietos | Solo en cámara: una caja vale como persona cuando se desplazó o cambió de tamaño; lo que nunca se mueve se ignora |
| Sentido de entrada | Opción en el menú para elegir hacia qué lado se entra (`INVERTIDO`) |
| Calidad de detección | Opción en el menú: Rápida (320), Media (480) o Precisa (640) (`IMGSZ`) |
| Acceso directo | Ícono de MOTIVA en el escritorio |
| Menú rediseñado | Tarjetas por sección, botones segmentados, logo, controles que se apagan cuando no aplican |
| Ventana de video rediseñada | Cabecera y panel por fuera del video (ya no lo tapan), misma letra y colores del menú |
| Configuración recordada | `motiva_config.json`: opciones del menú y posición de las líneas |
| Registros ordenados | Carpeta `registros/`, nombre del espacio en el archivo, sin archivos vacíos |
| Informe de sesión | Imagen con cinco cifras y la gráfica de ocupación en el tiempo |
| LED de alerta | Parpadea mientras la ocupación supera el aforo (GPIO17) |
| Página para el celular | Servidor web en la red local con medidor, contadores y gráfica en vivo |

### 29 de octubre de 2026: interfaz con CustomTkinter, arranque y memoria

Tras una revisión de diseño con herramientas de crítica de interfaces (ver `03_interfaz.md`, sección 3.9):

| Cambio | Detalle |
|---|---|
| Menú con CustomTkinter | Controles redondeados, botones segmentados y deslizador nuevo; dos columnas para caber en el monitor de 1360x768; tarjeta de ayuda "Durante el monitoreo"; Enter inicia; aforo mínimo 1 |
| Motivo de red neuronal | Encabezado ilustrado en el menú y, más tenue, en el video, el informe y la página del celular; fondo con un toque azul (`#11131c`) |
| Avisos propios | Cuadros de mensaje con el estilo de la app en vez de los de Tkinter, con mensajes que dicen cómo corregir el problema |
| Modelo precargado | La librería y el modelo se cargan en segundo plano mientras el menú está abierto; si no están listos al iniciar, se muestra "Preparando el detector"; cada sesión usa un modelo nuevo |
| Memoria | Al terminar una sesión se suelta su modelo; al encadenar sesiones el programa ocupa unos 150 MB menos |
| Casos extremos | Nombres largos recortados con "…" en el video y el informe; horas con formato h:mm:ss desde la primera hora; curva del informe resumida en sesiones largas |
| Página del celular | Íconos de estado dibujados, marcas verde y roja en entradas y salidas, barra del navegador según el tema, sin destello al tocar |

La explicación de cada punto está en `02_como_funciona.md` y `03_interfaz.md`; las mediciones que los respaldan, en `04_resultados_medidos.md`.

## 1.5 Lo que no cambió

- **La regla de conteo.** De la línea verde hacia la roja es entrada; de la roja hacia la verde es salida. El autor confirmó que esa lógica es la correcta y no se modificó.
- **El modelo.** Sigue siendo el YOLO11s de una clase entrenado por el autor. Solo cambió el formato en que se ejecuta. Se evaluó entrenar un YOLO11n más liviano para ganar velocidad y el autor decidió seguir con el modelo actual.
- **El formato del CSV.** Mismas cuatro columnas: `Tiempo, Entradas, Salidas, Ocupacion`.
