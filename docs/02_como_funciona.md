# 2. Cómo funciona por dentro

Todo está en `codigo/motiva_app.py`. Los nombres entre comillas invertidas son funciones, clases o constantes de ese archivo.

## 2.1 Arquitectura general

El programa tiene dos etapas: el menú (`iniciar_app`) y la sesión de monitoreo (`iniciar_video`). Durante una sesión trabajan varios hilos:

| Hilo | Clase o función | Qué hace |
|---|---|---|
| Principal | `iniciar_video` | Muestra cada imagen, aplica el conteo, dibuja la ventana y atiende el teclado y el mouse |
| Lectura | `LectorCamara` o `LectorVideo` | Lee la cámara o el archivo sin frenar al resto |
| Detección | `Detector` | Ejecuta el modelo y el seguimiento sobre las imágenes que le entrega el lector |
| LED | `LedAlerta` | Hace parpadear el LED cuando se le indica |
| Web | `PaginaWeb` (servidor) | Responde a los celulares que consultan el estado |
| Preparación del modelo | `precargar_modelo` | Carga la librería de detección y el modelo, y hace una primera detección de prueba, mientras el menú está abierto |

La separación entre lectura, detección y dibujo es lo que permite que el video se vea fluido aunque cada detección tarde entre 0,2 y 0,8 segundos en la Raspberry.

## 2.2 Lectura de la fuente

**Cámara (`LectorCamara`).** Se abre a 640x480 con un búfer de una sola imagen. El hilo lee sin parar y guarda únicamente la imagen más reciente, de modo que nunca se muestran ni se analizan imágenes atrasadas. El bucle principal y el detector piden "una imagen más nueva que la última que vi".

**Video (`LectorVideo`).** Lee el archivo por adelantado. Cada imagen pasa por `reducir`, que achica los videos cuyo lado mayor supera 960 px (`LADO_MAX_VIDEO`), y va a una cola para mostrarse. Una de cada `INTERVAL` imágenes se copia además a una segunda cola para el detector, junto con su instante dentro del video. Así, cuando a esa imagen le toca mostrarse, su detección ya está lista o casi lista.

## 2.3 Detección

`Detector` toma una imagen del lector y llama a `detectar`, que ejecuta:

```python
model.track(source=frame, persist=True, imgsz=imgsz, rect=True,
            tracker=TRACKER, conf=0.30, iou=0.35, classes=[0], verbose=False)
```

- **Modelo:** `modelos/best_junio_openvino_model`, un YOLO11s de una clase (`person`) en formato OpenVINO con entrada de tamaño variable. Se carga con la librería ultralytics.
- **`imgsz`:** el tamaño de entrada, que es la "calidad" del menú: 320 (Rápida), 480 (Media) o 640 (Precisa). Por defecto la cámara usa 320 y el video 640.
- **`rect=True`:** la entrada se ajusta a la forma de la imagen en vez de rellenarla hasta un cuadrado. Una imagen de cámara 640x480 a calidad 320 entra al modelo como 256x320.
- **`conf=0.30`, `iou=0.35`:** umbral de confianza y umbral de supresión de cajas repetidas.
- El detector mide cuánto tarda cada detección y guarda un promedio suavizado (`duracion`), que el modo video usa para repartir las imágenes en el tiempo.

**Carga del modelo.** La librería ultralytics no se importa al arrancar el programa: cargarla y hacer la primera detección tarda unos 15 a 17 segundos en la Raspberry. Un hilo (`precargar_modelo`) lo hace en segundo plano en cuanto aparece el menú, y deja listo un modelo ya probado. Al iniciar una sesión, el detector toma ese modelo (`tomar_modelo`); si el usuario pulsa INICIAR antes de que esté listo, el menú muestra "Preparando el detector" y espera (`esperar_modelo`). Cada sesión usa un modelo nuevo, para que el seguimiento empiece siempre desde cero, y al terminar la sesión su modelo se suelta (`cerrar_recursos`) antes de preparar el de la siguiente. Al cerrar el programa, se termina sin esperar a un modelo que se esté preparando.

En **cámara**, el detector trabaja sin parar, siempre sobre la imagen más reciente; el número de detecciones por segundo depende de la calidad elegida y de la carga del equipo. En **video**, analiza exactamente una de cada `INTERVAL` imágenes, así que el resultado es repetible.

## 2.4 Seguimiento

El seguimiento lo hace ByteTrack (incluido en ultralytics), configurado en `codigo/tracker_motiva.yaml`. Respecto al `bytetrack.yaml` original cambian dos valores:

| Parámetro | Original | MOTIVA | Motivo |
|---|---|---|---|
| `match_thresh` | 0.8 | 0.9 | Entre una detección y la siguiente la persona se mueve bastante; un umbral más permisivo evita perder el ID |
| `fuse_score` | True | False | No mezclar la confianza con el solapamiento al emparejar, por la misma razón |

Los demás valores quedan por defecto (`track_high_thresh` 0.25, `track_low_thresh` 0.1, `new_track_thresh` 0.25, `track_buffer` 30).

Antes del 10 de octubre se usaba el seguidor por defecto de ultralytics, que necesita ver a la persona en varias detecciones seguidas antes de darle un ID. Con pocas detecciones por segundo, la persona ya había cruzado las líneas cuando recibía el ID, y no se contaba. Las cifras de esa comparación están en `04_resultados_medidos.md`.

## 2.5 Conteo

**Zonas.** `get_zona` clasifica el centro de cada caja en una de tres zonas según su posición respecto a las dos líneas: `arriba` (antes de la línea verde), `medio` (entre las dos) y `abajo` (después de la roja). Con líneas verticales se usa la posición horizontal del centro, y los mismos nombres de zona.

**Regla.** Para cada persona con ID se compara su zona actual con la que tenía en la detección anterior (`zona_anterior`):

- de `arriba` a `medio` o `abajo`: se suma una **entrada**;
- de `medio` o `abajo` a `arriba`: se suma una **salida**.

Una precisión para el texto de la tesis: tal como está el código, el conteo se dispara al cruzar la **línea verde**, en un sentido o en el otro; las zonas `medio` y `abajo` se tratan igual. El autor describe la regla como "de la verde hacia la roja es entrada, de la roja hacia la verde es salida", que es el sentido del movimiento, y pidió expresamente no tocar esa lógica. Conviene que el libro la explique de forma que ambas cosas sean ciertas: el sentido lo dan las dos líneas y el evento se registra en la verde.

**Sentido de entrada (`INVERTIDO`).** Por defecto la verde va primero (a 1/3 del alto, o del ancho con líneas verticales) y la roja después (a 2/3), así que se entra hacia abajo o hacia la derecha. Con el sentido invertido las líneas intercambian su lugar y `get_zona` se refleja: `arriba` pasa a ser el lado de la verde que queda lejos de la roja. La regla no cambia.

**Ocupación.** `max(0, entradas - salidas)`. Nunca es negativa: si se cuentan salidas antes de que haya entradas, la ocupación se queda en cero.

**Reasignación de IDs.** Si el seguidor pierde a alguien y luego le da un ID nuevo, se perdería su zona anterior y con ella el cruce. Por eso, cuando aparece un ID nuevo, hereda la zona del ID perdido más cercano, siempre que esté a menos del 15 % del alto de la imagen (`REASIG_DIST_PCT`) y lleve perdido como mucho 3 detecciones (`REASIG_INFERENCIAS`).

## 2.6 Filtro de objetos quietos (solo cámara)

**Problema.** En la cámara del autor, el modelo marcaba como persona objetos que no lo eran, y con confianza alta: una cesta de ropa obtuvo entre 0,61 y 0,72, más que el propio autor sentado de espaldas (0,50 a 0,60). Subir el umbral de confianza no servía, porque eliminaba antes a la persona que al objeto.

**Solución.** Una caja solo "vale como persona" (se dibuja y se cuenta) después de haberse movido. Para cada ID se guarda un ancla con su posición, su tamaño y la hora (`ancla`). En cada detección:

- si el centro se desplazó al menos `MOVIMIENTO_MIN` (0,3) veces el lado mayor de la caja respecto al ancla, **o** el lado mayor cambió al menos `TAMANO_MIN` (35 %), el ID queda confirmado (`confirmados`) y el ancla se actualiza;
- si pasa más de `QUIETO_MAX` (10 segundos) sin cumplir ninguna de las dos condiciones, el ID deja de valer hasta que vuelva a moverse.

La segunda condición (cambio de tamaño) se agregó porque quien camina de frente hacia la cámara casi no se desplaza en la imagen: solo se agranda.

**El conteo no se pierde.** Mientras un ID no está confirmado se recuerda la zona donde apareció; cuando se confirma, se compara contra esa zona, de modo que el cruce se cuenta en ese momento.

**En video está apagado.** Con archivos de video el filtro no se aplica, porque escondía las cajas de personas que estaban paradas (entre 22 y 35 % de las cajas en las pruebas).

Con `MOVIMIENTO_MIN = 0` el filtro queda desactivado.

## 2.7 Adelanto de las cajas

Cada detección corresponde a una imagen de hace unas décimas de segundo, así que, sin corregir, la caja se dibuja detrás de la persona. `actualizar_velocidades` calcula la velocidad de cada ID entre sus dos últimas detecciones (suavizada 70/30 con la anterior) y el bucle dibuja la caja desplazada según `velocidad × tiempo transcurrido`, con un tope de `ADELANTO_MAX` (1 segundo).

El adelanto afecta **solo al dibujo**. El conteo usa siempre la posición detectada.

Efecto conocido: si alguien frena o gira de golpe, la caja se pasa un instante y se corrige con la siguiente detección.

## 2.8 Reparto de las imágenes en modo video

En video, el bucle muestra todas las imágenes y espera la detección de una de cada `INTERVAL`. Para que no salgan varias de golpe y luego una pausa, cada imagen se muestra con un paso de tiempo igual a `max(1 / fps_del_video, duracion_de_una_deteccion / INTERVAL)`. Es decir, el video va a su velocidad real si la detección alcanza, y si no, va más lento pero parejo.

## 2.9 Configuración recordada

`motiva_config.json` (junto al programa) guarda:

- las opciones del menú: nombre, aforo, fuente, ruta del video, intervalo, orientación, sentido y la calidad de cada fuente por separado;
- la posición de las líneas, por fuente (cámara o video) y por orientación, como **fracción** del alto o ancho de la imagen, para que sirvan con otra resolución.

Las opciones se guardan al pulsar INICIAR (`guardar_config`) y las líneas al terminar la sesión (`recordar_lineas`). El archivo se escribe primero con otro nombre y luego se reemplaza, para que no quede dañado si la Raspberry se apaga en ese instante. Si el archivo falta o está dañado, se usan los valores de fábrica. Hay un ejemplo en `codigo/ejemplo_motiva_config.json`.

## 2.10 Registro de la sesión

- **CSV.** Uno por sesión, en `registros/`, con nombre `motiva_<espacio>_<AAAAMMDD_HHMMSS>.csv`. Columnas: `Tiempo` (hora del reloj), `Entradas`, `Salidas`, `Ocupacion`. Se agrega una fila por cada conteo y se escribe a disco de inmediato. El archivo se crea con el primer conteo, así que una sesión sin conteos no deja archivo.
- **Historial en memoria.** `historial` guarda `(segundo de la sesión, entradas, salidas)` por cada conteo; lo usan el informe y la página web. En modo video, el "segundo de la sesión" es el del video, no el del reloj.
- **Informe.** Al terminar, si hubo conteos, `dibujar_informe` genera una imagen de 960x600 que se guarda como PNG con el mismo nombre del CSV. Ver `03_interfaz.md`.

## 2.11 Alerta física (LED)

`LedAlerta` controla el pin GPIO17 (pin físico 11) con la librería `gpiod`. Un hilo hace parpadear el LED (0,3 s encendido, 0,3 s apagado) mientras el bucle principal le indique que la ocupación supera el aforo, y lo deja apagado en caso contrario, al terminar la sesión y al salir del programa. Si el LED no puede prepararse (otro equipo, pin ocupado), el programa sigue funcionando sin él. `PIN_LED = None` lo desactiva.

Conexión prevista: ánodo del LED a una resistencia de 220 a 330 Ω y de ahí al pin físico 11; cátodo al pin físico 9 (tierra).

## 2.12 Página para el celular

Al abrir el menú arranca un servidor web (`http.server` de la librería estándar de Python) en el puerto 8080 de la Raspberry, en un hilo aparte. Atiende dos rutas:

- `/` entrega una página HTML autocontenida (sin recursos externos);
- `/estado` entrega un JSON con: espacio, si hay sesión activa, si está en pausa, fuente, entradas, salidas, ocupación, aforo, si está superado, segundos de sesión, ocupación máxima y su instante, y la curva de ocupación (hasta 240 puntos; en sesiones largas se resume por tramos conservando los máximos).

La página consulta `/estado` cada segundo. Es de solo lectura: no recibe datos ni permite controlar nada, y no transmite la imagen de la cámara. Solo es accesible desde la misma red local. `PUERTO_WEB = None` la desactiva.

## 2.13 Parámetros principales

Todos están al inicio de `motiva_app.py`.

| Constante | Valor | Significado |
|---|---|---|
| `MODEL_PATH` | `modelos/best_junio_openvino_model` | Modelo en uso |
| `IMGSZ_CAMARA` / `IMGSZ_VIDEO` | 320 / 640 | Calidad por defecto de cada fuente |
| `LADO_MAX_VIDEO` | 960 | Los videos más grandes se achican al leerlos |
| `TRACKER` | `modelos/tracker_motiva.yaml` | Configuración de ByteTrack |
| `REASIG_DIST_PCT` / `REASIG_INFERENCIAS` | 0,15 / 3 | Reasignación de IDs |
| `ADELANTO_MAX` | 1,0 s | Tope del adelanto de las cajas |
| `MOVIMIENTO_MIN` / `TAMANO_MIN` / `QUIETO_MAX` | 0,3 / 0,35 / 10 s | Filtro de objetos quietos |
| `MARGEN` | 15 px | Distancia para agarrar una línea con el mouse |
| `ALTO_CABECERA` / `ALTO_PANEL` | 56 / 108 px | Franjas de la ventana de video |
| `PIN_LED` | 17 | GPIO del LED de alerta |
| `PUERTO_WEB` | 8080 | Puerto de la página para el celular |
| `INTERVAL` | 5 (se elige en el menú, 1 a 10) | En video, se analiza 1 de cada `INTERVAL` imágenes |
