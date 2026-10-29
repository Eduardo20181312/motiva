# 5. Limitaciones, cosas no validadas y pendientes

Este documento existe para que la tesis no afirme más de lo que se comprobó. Cada punto dice qué se sabe y qué no.

## 5.1 Lo que no se ha validado

| Tema | Qué se hizo | Qué falta |
|---|---|---|
| Exactitud del conteo | Comparaciones entre configuraciones del propio sistema, con una corrida densa como referencia | Un conteo hecho a mano sobre los videos o en el sitio. Sin eso no se puede dar un porcentaje de acierto |
| Cámara en el sitio real | Pruebas con videos de terceros, y con la cámara sobre un escritorio en la casa del autor | La cámara montada a la altura del techo mirando a la entrada, que es como se va a usar |
| Conteo en vivo | Videos de prueba entregados al programa en tiempo real, como si fueran la cámara | Sesiones reales con personas cruzando frente a la cámara instalada |
| LED de alerta | Se comprobó leyendo el nivel eléctrico del pin: parpadea solo con el aforo superado | Verlo funcionar con un LED físico conectado |
| Página para el celular | Revisada con un navegador en tamaño de teléfono; el autor la abrió en su celular y pidió mejorar el diseño, que se rehízo | Confirmación del autor sobre el diseño final en un teléfono real |
| Sesiones largas | Sesiones de segundos a pocos minutos; la página web se probó con datos simulados de dos horas y media | Una sesión real de varias horas (estabilidad, temperatura, tamaño del registro) |

## 5.2 Limitaciones conocidas del sistema

**Velocidad de detección.** En la Raspberry Pi 4, sin acelerador, el modelo YOLO11s tarda unos 220 ms por detección a calidad Rápida y más de 600 ms a calidad Precisa. En vivo eso son entre 2 y 3 detecciones por segundo a calidad Rápida. Las pruebas indican que el conteo se sostiene con unas 3 detecciones por segundo o más y se degrada por debajo (sección 4.10 de los resultados). El sistema en vivo trabaja cerca de ese límite.

**Personas pequeñas o lejanas.** A calidad Rápida el modelo deja de ver a personas pequeñas en la imagen. En una escena de centro comercial con mucha gente lejana, en vivo se contó cerca de la mitad de lo que da el modo video a calidad Precisa. La recomendación es que la entrada ocupe buena parte de la imagen.

**Multitudes.** El autor observó que con una gran multitud el sistema deja de contar a algunas personas, y lo considera una limitación aceptable.

**Punto de vista.** El modelo rinde bien con la cámara en alto mirando hacia abajo y mal con personas vistas de frente a la altura de los ojos (sección 4.9). No es un detector de personas de uso general.

**Falsos positivos con objetos.** El modelo confunde algunos objetos (ropa amontonada, bolsos) con personas, a veces con confianza alta. El filtro de objetos quietos lo compensa en cámara, pero es un parche: no vuelve más preciso al modelo. Tiene dos efectos secundarios: una persona que permanece quieta más de 10 segundos deja de mostrarse hasta que se mueve, y un objeto puede llegar a confirmarse si alguien pasa por delante y altera su caja (se corrige solo a los 10 segundos).

**Cajas adelantadas.** Cuando alguien frena o gira de golpe, la caja dibujada se pasa un instante. Es solo visual y no afecta el conteo.

**Ocupación nunca negativa.** Si se cuentan salidas antes que entradas (por ejemplo, al empezar con gente ya adentro), la ocupación queda en cero y las cifras dejan de cuadrar con la realidad hasta que alguien entre.

**Arranque.** Los primeros segundos de cada sesión no hay detecciones, porque el modelo se está cargando.

**Carga del equipo.** Otros programas abiertos en la Raspberry reducen las detecciones por segundo (de unas 2,2 a unas 1,8 en las pruebas).

**Imagen de la cámara.** En la cámara usada, la imagen sale algo empañada y con zonas quemadas frente a paredes claras. No se evaluó otra cámara.

**Tamaño de la pantalla.** El menú mide 1010x635 px: cabe en el monitor del proyecto (1360x768) y en cualquiera de 1024x700 o más, pero no en pantallas pequeñas, como una táctil de 7 pulgadas.

**Teclado.** Los botones segmentados del menú (CustomTkinter) no muestran cuál opción tiene el foco cuando se navega solo con el teclado; con el mouse funcionan normal. Los campos de texto sí marcan el foco con borde amarillo.

**Primera sesión tras abrir.** Si se pulsa INICIAR apenas abre el programa, hay que esperar a que termine de prepararse el detector: unos 15 a 20 segundos en total desde que se abre, con el aviso "Preparando el detector" en pantalla.

**Página web.** Solo funciona dentro de la misma red local, sin cifrado ni contraseña: cualquiera conectado a esa red puede ver los contadores. No muestra el video. La dirección cambia si el router le asigna otra IP a la Raspberry.

## 5.3 Lo que no se sabe y hay que preguntarle al autor

- **Las métricas de entrenamiento del modelo en uso.** El sistema usa los pesos de un entrenamiento de junio de 2026. En la Raspberry solo quedaron guardadas las métricas de un entrenamiento distinto, de abril de 2026 (ver `06_entorno_e_instalacion.md`). No uses las de abril como si fueran del modelo en uso.
- **El dataset.** La ruta registrada en el entrenamiento es `/content/person-2/data.yaml`, lo que sugiere un dataset llamado "person" en su versión 2, descargado en Google Colab (posiblemente desde Roboflow; esto es una suposición). El origen, el tamaño y la composición del dataset los conoce el autor.
- **Qué versión del sistema describe hoy el libro.** En `codigo/versiones_anteriores/` hay varias; no se sabe cuál corresponde al texto actual.
- **El sitio de instalación definitivo.** El autor indicó que será variable, respetando la altura (techo) y la posición de la cámara apuntando a la entrada.

## 5.4 Decisiones del autor

- **Seguir con el modelo actual.** Se le propuso entrenar un YOLO11n (más liviano) con el mismo dataset para ganar detecciones por segundo, y prefirió no hacerlo.
- **No agregar un modelo estándar para vistas de frente,** porque la cámara irá en el techo.
- **No agregar un nivel de calidad "Muy rápida" (256)** para la cámara, aunque en las pruebas dio el mismo conteo con más detecciones por segundo. Considera que el sistema está bien como está.
- **No tocar la regla de conteo** de las líneas verde y roja.
- **No advertir en el menú que Media y Precisa empeoran el conteo con la cámara**, aunque la revisión de diseño lo sugirió.
- **El motivo de red neuronal para los fondos,** elegido entre tres propuestas (circuito impreso, red neuronal y escena de conteo).

## 5.5 Posibles mejoras futuras

Sirven para un capítulo de trabajo futuro. Ninguna está implementada.

- Validar la exactitud con conteo manual en el sitio real.
- Entrenar un modelo más liviano (YOLO11n) o agregar ejemplos negativos (objetos, fondos) al dataset para reducir falsos positivos.
- Un nivel de calidad más rápido para la cámara (tamaño 256 o 224).
- Usar un acelerador de inferencia o una Raspberry Pi más reciente.
- Arranque automático del sistema al encender la Raspberry.
- Proteger la página web con contraseña, o permitir verla fuera de la red local.
- Agregar un zumbador además del LED.
