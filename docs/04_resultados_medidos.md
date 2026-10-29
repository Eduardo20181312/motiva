# 4. Resultados medidos

Todas las cifras de este documento se midieron en la Raspberry Pi 4 del proyecto entre el 10 y el 12 de octubre de 2026. Antes de usarlas en la tesis, lee la sección 4.1: dice qué significan y qué no.

## 4.1 Cómo leer estas cifras

- **No hay conteo manual.** Ninguna cifra de entradas y salidas se comparó contra un conteo hecho por una persona. Las "referencias" son corridas del propio sistema con detección más densa (más imágenes analizadas y calidad máxima). Sirven para comparar configuraciones entre sí, no para afirmar una exactitud absoluta.
- **El modo video es repetible; el modo en vivo no.** En video se analiza siempre la misma imagen de cada `INTERVAL`, así que el conteo sale igual cada vez. En vivo depende del momento exacto en que cae cada detección, y de una corrida a otra puede variar en una persona.
- **"En vivo" significa cámara simulada.** Para tener escenas repetibles, las pruebas en vivo se hicieron entregándole al programa un video de prueba en tiempo real, como si fuera la cámara. No son pruebas con la cámara montada en un sitio real.
- **La velocidad depende de la carga del equipo.** Las mediciones se hicieron con el editor de código y Claude Code abiertos en la misma Raspberry, lo que le quita velocidad a la detección (sección 4.11). Los tiempos "aislados" se midieron llamando al modelo solo, sin el resto del programa.
- **Formato de los conteos:** entradas / salidas.

### Videos de prueba

Son videos de terceros que el autor tenía en la Raspberry. No están en esta carpeta.

| Archivo | Tamaño | Duración | Escena |
|---|---|---|---|
| `videoa.mp4` | 768x432, 30 fps | 17 s | Plaza vista desde arriba, pocas personas |
| `videon.mp4` | 768x432, 25 fps | 11 s | Escaleras, personas cercanas |
| `videoc.mp4` | 768x432, 25 fps | 10 s | Entrada de edificio vista desde arriba |
| `videoo.mp4` | 720x1280, 30 fps | 34 s | Centro comercial, mucha gente pequeña y lejana |
| `videoo2.mp4` | 1080x1920, 30 fps | 38 s | Entrada vista desde arriba |
| `video.mp4` | 640x360, 30 fps | 21 s | Paseo peatonal a la altura de los ojos, gente de frente y de espaldas |
| `videop.mp4` | 464x832, 60 fps | 24 s | Salón de clase a la altura de los ojos |

## 4.2 Punto de partida (10 de octubre)

Tiempo por detección con ONNX Runtime, antes de cualquier cambio:

| Modelo | Tiempo por detección |
|---|---|
| `best.onnx` original (YOLO11s a 640x640) | unos 1445 ms |
| El mismo modelo exportado a 320x320 | unos 417 ms |

Estas dos cifras se tomaron con la memoria del equipo casi llena, así que son más altas que las de secciones posteriores.

Con la cámara, antes: una detección cada 1,3 s aproximadamente, con la imagen congelada entre una y otra. Después de separar lectura y detección en hilos y bajar la cámara a 320: video a unos 20 fps y unas 2,7 detecciones por segundo.

## 4.3 Efecto del seguidor (10 de octubre)

**En vivo** (cámara simulada). La columna de referencia es el conteo que daba el programa en modo video en ese momento.

| Video | Modo video (referencia) | En vivo, seguidor anterior | En vivo, ByteTrack ajustado |
|---|---|---|---|
| `videoc.mp4` | 2 / 2 | 0 / 0 | 2 / 2 |
| `videon.mp4` | 4 / 4 | 1 / 0 | 6 / 4 |
| `videoa.mp4` | 6 / 6 | 1 / 0 | 8 / 7 |

**En modo video.** Referencia densa para `videon.mp4` (una de cada 2 imágenes, tamaño 640): 6/4 con el seguidor anterior y 6/5 con el nuevo.

| Configuración | `videon.mp4` | `videoa.mp4` | Fluidez |
|---|---|---|---|
| Seguidor anterior, intervalo 5, tamaño 640 | 3 / 4 | 6 / 6 | 5 a 6 fps |
| Seguidor anterior, intervalo 10, tamaño 640 | 3 / 3 | 0 / 0 | 10 a 11 fps |
| ByteTrack ajustado, intervalo 5, tamaño 640 | 7 / 5 | 7 / 7 | 5 a 6 fps |
| ByteTrack ajustado, intervalo 10, tamaño 640 | 6 / 6 | 6 / 7 | 10 a 11 fps |
| ByteTrack ajustado, intervalo 8, tamaño 480 | 7 / 5 | 6 / 7 | 13 a 14 fps |
| ByteTrack ajustado, intervalo 10, tamaño 384 | 6 / 6 | 5 / 6 | 17 a 22 fps |

Lectura: con el seguidor anterior, subir el intervalo a 10 dañaba el conteo (0/0 en `videoa.mp4`); con ByteTrack ajustado se mantiene.

## 4.4 Adelanto de las cajas (10 de octubre)

Distancia entre la caja dibujada y la posición real de la persona, mediana para personas caminando, en videos de 768 px de ancho pasados como cámara en vivo:

| Retraso de la detección | Desfase sin adelanto | Desfase con adelanto |
|---|---|---|
| 0,3 a 0,4 s | 23 a 34 px | 6 a 10 px |
| 0,6 a 0,75 s | 45 a 68 px | 11 a 19 px |

## 4.5 ONNX Runtime frente a OpenVINO (12 de octubre)

Mismo modelo y mismos pesos en los dos formatos.

**Tiempo por detección, aislado** (mediana sobre 25 imágenes de `videoo.mp4`):

| Caso | ONNX Runtime | OpenVINO | Mejora |
|---|---|---|---|
| Imagen de cámara 640x480, tamaño 320 | 285 ms | 217 ms | 31 % más detecciones por segundo |
| Imagen de video 540x960, tamaño 640 | 827 ms | 627 ms | 32 % |

**Igualdad de resultados:** en esas 25 imágenes, el mismo número de cajas con los dos formatos (41 a tamaño 320 y 307 a tamaño 640), diferencia máxima de 0,1 px en las cajas y ninguna en la confianza.

**Programa completo, modo video, intervalo 10, tamaño 640:**

| Video | ONNX Runtime | OpenVINO | Conteo |
|---|---|---|---|
| `videoo.mp4` | 8,2 fps (1031 ms por detección) | 10,4 fps (814 ms) | 13 / 12 con ambos |
| `videoa.mp4` | 9,5 fps (896 ms) | 11,3 fps (712 ms) | 6 / 7 con ambos |

**Programa completo, cámara simulada, tamaño 320:** de 1,5 a 2,2 detecciones por segundo, con unos 28 fps mostrados en ambos casos.

También se probó el formato NCNN el 10 de octubre: en esta Raspberry no fue más rápido que ONNX Runtime y además bloqueaba los demás hilos del programa.

## 4.6 Calidad de detección (12 de octubre)

**Tiempo por detección, aislado, con OpenVINO** (mediana sobre 20 imágenes):

| Calidad (tamaño) | Imagen de cámara 640x480 | Imagen de video 540x960 |
|---|---|---|
| Rápida (320) | 224 ms | 174 ms |
| Media (480) | 473 ms | 362 ms |
| Precisa (640) | 767 ms | 618 ms |

**Conteo y fluidez en modo video, intervalo 10:**

| Calidad | `videoa.mp4` | `videoo.mp4` |
|---|---|---|
| Precisa (640) | 6 / 7, a 11 fps | 13 / 12, a 10 fps |
| Media (480) | 6 / 7, a 16 fps | 7 / 11, a 15 fps |
| Rápida (320) | 6 / 7, a 22 fps | 6 / 8, a 22 fps |

Lectura: con pocas personas y cercanas la calidad no cambia el conteo; con mucha gente pequeña y lejana, bajar la calidad pierde cerca de la mitad de las entradas.

## 4.7 Objetos confundidos con personas y filtro de objetos quietos (12 de octubre)

**Confianza que el modelo asignó en la cámara real** (habitación del autor, calidad Rápida, 86 detecciones en 40 s):

| Objeto en la escena | Confianza | Cuánto se movió su caja (fracción de su tamaño) |
|---|---|---|
| Cesta de ropa | 0,61 a 0,72 | 0,02 |
| Persona sentada de espaldas (el autor) | 0,31 a 0,78; habitualmente 0,50 a 0,60 | hasta 0,43 |
| Segunda cesta | 0,30 a 0,43 | hasta 0,56 (la caja cambiaba de forma) |
| Bolso colgado | 0,30 a 0,47 | 0,04 |

Además, en `videoo.mp4` a calidad Rápida, 21 de las 41 cajas de personas reales tenían confianza menor a 0,45. Por las dos razones se descartó subir el umbral de confianza y se optó por el filtro de movimiento.

**Efecto del filtro con la cámara real:** en 40 s, las dos cestas y el bolso no se dibujaron ninguna vez; sin el filtro se dibujaban de forma continua.

**Efecto del filtro si se aplicara en video** (por eso quedó apagado en ese modo):

| Video | Cajas dibujadas sin filtro | Con filtro | Conteo |
|---|---|---|---|
| `videoo.mp4` | 11 753 | 9 004 (23 % menos) | igual, 13 / 12 |
| `videoa.mp4` | 3 297 | 2 153 (35 % menos) | igual, 6 / 7 |
| `videon.mp4` | 1 969 | 1 534 (22 % menos) | igual, 7 / 5 |

**Personas que caminan de frente.** La primera versión del filtro solo aceptaba desplazamiento lateral. En `video.mp4` (gente caminando de frente y de espaldas), pasado como cámara en vivo:

| Versión del filtro | Cajas mostradas por imagen |
|---|---|
| Sin filtro | 1,4 a 1,5 |
| Solo desplazamiento | 0,38 |
| Desplazamiento o cambio de tamaño (versión final) | 1,07 |

## 4.8 Sentido de entrada invertido (12 de octubre)

Comprobación en modo video con `videoa.mp4`, colocando la línea verde en el mismo sitio en los dos sentidos:

| Líneas | Sentido normal | Sentido invertido |
|---|---|---|
| Horizontales | 8 / 7 | 7 / 8 |
| Verticales | 0 / 2 | 2 / 0 |

Las entradas y las salidas se intercambian exactamente, como debe ser.

## 4.9 El modelo según el punto de vista de la cámara (12 de octubre)

Comparación del modelo del proyecto con modelos YOLO11 estándar preentrenados en COCO (clase persona), sobre las mismas imágenes. Personas detectadas por imagen, con umbral de confianza 0,30:

| Escena | Tamaño | Modelo del proyecto | YOLO11n COCO | YOLO11s COCO |
|---|---|---|---|---|
| `video.mp4`, a la altura de los ojos | 320 | 4,1 | 6,6 | 8,0 |
| | 640 | 6,2 | 8,9 | 9,6 |
| `videop.mp4`, salón a la altura de los ojos | 320 | 5,3 | 3,0 | 4,8 |
| | 640 | 7,0 | 6,5 | 7,3 |
| `videoa.mp4`, desde arriba | 320 | 5,9 | 0,6 | 3,0 |
| | 640 | 7,0 | 3,8 | 3,9 |
| `videoo2.mp4`, entrada desde arriba | 320 | 4,5 | 4,3 | 4,3 |
| | 640 | 4,3 | 4,3 | 4,5 |

No hay etiquetas de referencia, así que esto no mide exactitud: mide cuántas detecciones entrega cada modelo. Lectura: el modelo del proyecto rinde mejor que los estándar en vistas desde arriba (hasta el doble en la plaza) y peor con personas vistas de frente a la altura de los ojos (cerca de la mitad). Esto respalda la decisión de montar la cámara en alto, mirando hacia abajo.

## 4.10 Detecciones por segundo y conteo; en vivo frente a video (12 de octubre)

**Cuántas detecciones por segundo hacen falta.** `videoa.mp4` en modo video, variando el intervalo. La referencia densa (tamaño 640, 10 detecciones por segundo) da 7 / 7.

| Detecciones por segundo de video | Tamaño | Conteo |
|---|---|---|
| 5 | 320 | 6 / 7 |
| 3 | 320 | 6 / 7 |
| 2 | 320 | 3 / 2 |
| 1,5 | 320 | 1 / 0 |

Lectura: en esta escena el conteo se sostiene con 3 o más detecciones por segundo y se desploma por debajo.

**En vivo, cámara simulada en formato 4:3 como la cámara real.** `videoa.mp4`, referencia 7 / 7:

| Calidad | Detecciones por segundo | Conteo en vivo |
|---|---|---|
| Rápida (320) | 2,6 a 2,8 | 8 / 7 y 7 / 6 (dos corridas) |
| Media (480) | 1,3 | 6 / 1 |
| Precisa (640) | 0,8 | 2 / 0 |
| Tamaño 256 (no está en el menú) | 3,9 a 4,2 | 8 / 7 |
| Tamaño 224 (no está en el menú) | 4,8 | 8 / 7 |

**Otras escenas, en vivo a calidad Rápida:**

| Video | Referencia | En vivo |
|---|---|---|
| `videon.mp4` | 8 / 6 (densa, tamaño 640) | 6 / 4 |
| `videoo.mp4` | 13 / 12 (modo video, Precisa) | 5 / 4 (y 8 / 11 a calidad Media) |

Lectura: con personas cercanas y grandes en la imagen, el conteo en vivo a calidad Rápida es comparable al del modo video. Con mucha gente pequeña y lejana, en vivo se cuenta alrededor de la mitad, porque en tiempo real no alcanza el tiempo para la calidad Precisa. En cámara, las calidades Media y Precisa empeoran el conteo de personas en movimiento, porque reducen las detecciones por segundo.

## 4.11 Costo de la interfaz y efecto de la carga del equipo (12 de octubre)

**Tiempo para dibujar la ventana de video** (`dibujar_ui`, mediana, aislado):

| Imagen | Diseño anterior | Diseño nuevo |
|---|---|---|
| 640x480 | 6,8 ms | 5,9 ms |
| 540x960 | 10,8 ms | 5,7 ms |

**Versión anterior frente a versión actual del programa**, misma prueba de cámara simulada y misma carga del equipo, dos corridas de cada una:

| Versión | Detecciones por segundo | Imágenes mostradas por segundo |
|---|---|---|
| Antes del rediseño de la interfaz | 1,88 y 1,80 | 28,1 y 28,3 |
| Actual | 1,84 y 1,76 | 26,8 y 26,8 |

Lectura: los cambios de interfaz, el informe, el LED y la página web no redujeron de forma apreciable la velocidad de detección.

**Carga del equipo.** En la misma prueba, el programa logró unas 2,2 detecciones por segundo con el equipo menos cargado y unas 1,8 con el editor de código y Claude Code trabajando. Durante las mediciones la temperatura fue de 45,7 °C y no hubo limitación por temperatura ni por voltaje.

## 4.12 Comprobaciones de las salidas nuevas (12 de octubre)

- **Configuración recordada:** tras mover las líneas en una sesión, la siguiente abrió con las líneas en la misma posición exacta; tras cambiar todas las opciones del menú, al reabrir volvieron iguales; con el archivo dañado, el menú abrió con los valores de fábrica sin error.
- **Registros:** con conteos se generan el CSV y el PNG; sin conteos no se crea ninguno.
- **LED:** en una sesión de video con aforo 0, se leyó el nivel del pin varias veces por segundo. Con el aforo superado, el pin estuvo encendido en 48 de 102 lecturas (parpadeo de mitad y mitad); sin superarlo, en 0 de 272; y quedó apagado al terminar. No se probó con un LED físico conectado.
- **Página web:** se revisó con un navegador en tamaño de teléfono en cuatro estados y en tema claro y oscuro. Una sesión simulada de dos horas y media con 900 conteos produjo una respuesta de 3,5 KB por consulta (238 puntos de curva).

## 4.13 La cámara

Cámara web USB que el sistema identifica como "DV20 USB". Ofrece hasta 1920x1080 a 30 fps en formato MJPG. El programa la abre a 640x480 y recibe formato YUYV a unos 19 fps medidos (22 fps nominales). La resolución de la cámara no limita la detección: el modelo reduce cada imagen al tamaño de la calidad elegida (320 en Rápida).

## 4.14 Interfaz con CustomTkinter, arranque y memoria (29 de octubre)

**Tiempo hasta ver el menú**, desde que se abre el programa:

| Versión | Tiempo |
|---|---|
| Antes (la librería de detección se cargaba al arrancar) | unos 8 s |
| Ahora (la librería se carga en segundo plano, después de mostrar el menú) | entre 1,6 y 6 s según la carga del equipo; lo habitual, 2 a 4 s |

Cargar la librería de detección antes de mostrar el menú lo demoraba unos 3 s más incluso en segundo plano, porque competía con el dibujo de la ventana; por eso arranca 0,4 s después de que el menú aparece.

**Tiempo hasta la primera detección.** Por separado, la librería tarda unos 6 s en cargarse y la primera detección unos 11,5 s más. Con la carga en segundo plano:

- si el usuario tarda unos 15 a 20 s en el menú, al pulsar INICIAR la primera caja aparece unos 3 s después de abrirse la ventana de video (antes, unos 11,5 s);
- en el peor caso (INICIAR a los 2,5 s de abrir, prueba con cámara simulada), el cuadro "Preparando el detector" aparece de inmediato, la ventana de video se abre a los 17 s y la primera detección llega a los 20 s de haber abierto el programa.

Una versión intermedia esperaba al modelo con la ventana de video ya abierta; en la misma prueba la primera detección tardó 79 s, porque el dibujo continuo del video competía con la carga. Por eso la espera se hace en el menú.

**Memoria del programa** al encadenar sesiones (una sesión corta de video y luego la preparación del modelo de la siguiente):

| Momento | Antes del arreglo | Después |
|---|---|---|
| Al terminar la sesión | 606 MB | 452 MB |
| Con el modelo de la siguiente sesión listo | 752 MB | 600 MB |

**El conteo no cambió:** en modo video, `videoa.mp4` 6 / 7, `videoo.mp4` 13 / 12 y `videon.mp4` 7 / 5, iguales a los de antes; en vivo con cámara simulada, `videoa.mp4` 8 / 7.

**Costo del dibujo:** con la red neuronal en la cabecera, dibujar la ventana de video tarda unos 7 ms por imagen (768x432), porque la cabecera se prepara una sola vez.

**Página del celular:** el detector automático de la skill *impeccable* no encontró problemas, ni en el código ni abierta en Chromium. La página pesa unos 21 KB.
