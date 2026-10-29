# 3. La interfaz

Las capturas citadas están en `figuras/`; `figuras/INDICE_FIGURAS.md` explica cómo se obtuvo cada una. Este documento describe la interfaz al 29 de octubre de 2026; la sección 3.10 resume qué cambió respecto a versiones anteriores.

## 3.1 Identidad visual

Menú, ventana de video, informe, cuadros de mensaje y página web comparten una misma apariencia, definida en constantes al inicio del programa (`C_*`):

| Elemento | Valor |
|---|---|
| Fondo | `#11131c` (casi negro, con un toque azul) |
| Tarjetas | `#1e2127`, con borde `#2e333d` |
| Texto principal / secundario | `#e8eaed` / `#8b93a1` |
| Color de marca | Amarillo `#ffc800` |
| Entrada / salida (líneas y contadores del video) | Verde `#3ddc64` / rojo `#f04a4a` |
| Curva de las gráficas | Azul `#3987e3` |
| "Aforo superado" en gráficas | Rojo `#d03b3b` |
| Tipografía | Nunito Sans |
| Motivo gráfico | Una red neuronal estilizada: nodos azules con conexiones finas y un recorrido resaltado en amarillo |

**El motivo de red neuronal.** Alude a la inteligencia artificial que usa el sistema. Es un único dibujo generado por el programa (`red_neuronal`, con semilla fija, así que sale siempre igual) que aparece en el encabezado del menú, en la cabecera de la ventana de video, en el informe y en la página del celular. En todos los casos se desvanece hacia la izquierda, para no estorbar al logo y al título, y fuera del menú va más tenue para no quitarle legibilidad a los datos. El autor lo eligió entre tres propuestas: circuito impreso, red neuronal y una escena de conteo.

El par azul y rojo de las gráficas se verificó con una herramienta de validación de paletas: se distinguen sobre el fondo oscuro también con las formas comunes de daltonismo. El rojo se reserva para "aforo superado" y siempre va acompañado de un texto o un ícono, nunca solo.

El ícono de la aplicación (`figuras/icono_motiva.png`) es una M amarilla sobre fondo oscuro con una línea verde y una roja, que representan las dos líneas de conteo.

## 3.2 Acceso directo

En el escritorio de la Raspberry hay un ícono "MOTIVA" (`codigo/MOTIVA.desktop`) que abre el programa con doble clic, sin terminal ni editor de código.

## 3.3 Menú de configuración

Figuras: `menu_camara.png`, `menu_video_lineas_verticales.png`.

Hecho con la librería **CustomTkinter**, que da a Tkinter controles con bordes redondeados, botones segmentados y un deslizador moderno. La ventana mide 1010x635 px, abre centrada y está organizada en **dos columnas**, para caber en pantallas de 768 px de alto (el monitor del proyecto es de 1360x768).

**Encabezado.** De lado a lado: el logo, "MOTIVA", "Sistema de monitoreo de ocupación" y "UIS · Ingeniería Electrónica" a la izquierda, y la red neuronal a la derecha.

**Columna izquierda**

*Espacio*
- *Nombre*: texto libre; aparece en la ventana de video, el informe, la página web y el nombre del archivo de registro.
- *Aforo máximo*: número entero de personas, de 1 en adelante.

*Fuente de video*
- *Fuente*: Cámara web o Video.
- *Archivo*: ruta del video, con un botón Buscar. Solo se activa con Video.
- *Intervalo*: de 1 a 10, con un deslizador; el texto al lado dice "analiza 1 de cada N imágenes". Solo se activa con Video.
- *Calidad*: Rápida, Media o Precisa (tamaño de entrada del modelo: 320, 480 o 640). Cada fuente recuerda la suya; por defecto, Rápida en cámara y Precisa en video.

**Columna derecha**

*Conteo*
- *Líneas*: Horizontales o Verticales.
- *Se entra*: el sentido de entrada. Los nombres cambian con la orientación: Hacia abajo / Hacia arriba con líneas horizontales, Hacia la derecha / Hacia la izquierda con verticales.

*Durante el monitoreo* (ayuda): qué hace el mouse (arrastrar las líneas), la tecla Espacio (pausa o reanuda), la tecla Q (termina la sesión y muestra el informe) y la dirección de la página para el celular.

**Abajo:** el botón INICIAR SISTEMA, de lado a lado, y la versión del programa.

Comportamiento:
- Las opciones son botones segmentados: el elegido queda resaltado en amarillo, con el texto en oscuro.
- Los controles que no aplican a la fuente elegida se muestran apagados.
- El campo de texto en uso se marca con borde amarillo.
- La tecla Enter equivale a pulsar INICIAR SISTEMA.
- Antes de iniciar se valida que el aforo sea un entero de 1 en adelante y que el nombre no esté vacío; si algo falla, sale un aviso que explica qué corregir y el cursor vuelve a ese campo.
- El menú abre con lo que se usó la última vez.
- Mientras el menú está abierto, el modelo de detección se prepara en segundo plano (sección 3.6).
- Al terminar una sesión, el menú vuelve a aparecer para iniciar otra.

## 3.4 Ventana de monitoreo

Figuras: `ventana_video_deteccion.png`, `ventana_video_vista_superior.png`, `ventana_video_lineas_verticales.png`, `ventana_video_aforo_superado.png`, `ventana_video_en_pausa.png`, `ventana_video_preparando.png`, `ventana_camara_en_vivo_simulada.png`.

La imagen que se muestra la arma `dibujar_ui` en tres franjas apiladas, de modo que la cabecera y el panel **no tapan el video**:

**Cabecera (56 px).** Logo, "MOTIVA" y el nombre del espacio a la izquierda; la red neuronal, tenue, en el centro; a la derecha, el tiempo de la sesión y el estado: "EN VIVO" con un punto rojo (cámara), "VIDEO" (archivo) o "PAUSADO". El tiempo se muestra como mm:ss y desde la primera hora como h:mm:ss. Si el nombre del espacio es muy largo, se recorta con "…" para no chocar con el estado.

**Video.** Sobre la imagen se dibujan:
- la línea verde con la etiqueta ENTRADA y la línea roja con la etiqueta SALIDA;
- una caja verde por cada persona, con la etiqueta `PERSON ID n`;
- una franja roja "AFORO SUPERADO" en la parte superior cuando la ocupación pasa del aforo;
- un recuadro "PAUSADO" en el centro durante la pausa;
- un aviso "Preparando el detector…" abajo, hasta que llega la primera detección.

**Panel (108 px).** Cuatro cifras: ENTRADAS (verde), SALIDAS (rojo), OCUPACIÓN (amarillo, o rojo si se supera el aforo) y AFORO MÁX. Debajo, una barra de nivel de ocupación con su porcentaje: verde por debajo del 70 %, naranja desde el 70 % y roja al 100 %. En la última línea, el recordatorio de controles y la dirección de la página para el celular.

Controles:
- **Mouse:** arrastrar una línea para moverla. Las líneas no se pueden cruzar entre sí (mantienen al menos 30 px de separación).
- **ESPACIO:** pausa y reanuda. En pausa se pueden seguir moviendo las líneas.
- **Q:** termina la sesión.

El texto se dibuja con la librería Pillow y la tipografía Nunito Sans (`poner_texto`, `poner_chapa`), lo que permite tildes y una letra igual a la del menú; la letra pequeña se dibuja al doble de tamaño y se reduce, para que no queden huecos disparejos entre letras. Cada texto se dibuja una sola vez y se reutiliza, y la cabecera con la red se prepara una vez por tamaño de ventana, para no gastar tiempo en cada imagen.

La ventana se dimensiona según el tamaño del video y la pantalla, y se centra.

## 3.5 Informe de sesión

Figuras: `ventana_informe.png`; ejemplos reales en `ejemplos/*.png`.

Al terminar una sesión con al menos un conteo, se abre una ventana con el informe y un botón Cerrar (también se cierra con Enter o Escape). El informe es una imagen de 960x600 px que también queda guardada como PNG junto al CSV. Contiene:

- **Encabezado:** espacio, fecha y hora de inicio, fuente (Cámara web o nombre del video) y duración, con la red neuronal tenue a la derecha. Un nombre de espacio muy largo se recorta con "…".
- **Cinco cifras:** entradas, salidas, ocupación final, ocupación máxima (con el instante en que ocurrió) y tiempo sobre el aforo (duración y porcentaje de la sesión, o "Nunca").
- **Gráfica "Ocupación durante la sesión":** curva escalonada (la ocupación cambia de golpe con cada conteo), con relleno suave, eje vertical en personas y eje horizontal en tiempo de sesión. Se rotulan solo el máximo y el valor final. Una línea roja marca el aforo máximo y los tramos en que se superó quedan sombreados en rojo. En sesiones con más conteos que pixeles disponibles, la curva se resume a un punto por columna para que no se vuelva una mancha.

Si el aforo es más de tres veces la ocupación máxima alcanzada, la línea del aforo no se dibuja (aplastaría la curva) y el subtítulo lo indica.

Si la sesión no tuvo conteos, no se genera informe; sale un aviso que lo explica.

## 3.6 Avisos y espera del detector

Figuras: `aviso_error.png`, `dialogo_preparando_detector.png`.

**Avisos.** Todos los mensajes (errores de configuración, problemas con la cámara o el video, sesión sin conteos) usan un cuadro propio con el aspecto de la app (`aviso`): un punto de color (rojo para errores, amarillo para información), un título, el mensaje en lenguaje sencillo con la forma de corregir el problema, y un botón "Entendido". Reemplazan a los cuadros grises estándar de Tkinter.

**Espera del detector.** Cargar la librería de detección y hacer la primera detección tarda unos 15 a 17 segundos en la Raspberry. Para que el usuario no espere a ciegas:
- el modelo se empieza a preparar en segundo plano en cuanto aparece el menú, mientras el usuario revisa las opciones;
- si al pulsar INICIAR todavía no está listo, aparece el cuadro "Preparando el detector" con una barra en movimiento, y la sesión empieza cuando termina;
- ya en la ventana de video, el aviso "Preparando el detector…" se mantiene hasta la primera detección.

## 3.7 Página para el celular

Figuras: `celular_aforo_completo_oscuro.png`, `celular_aforo_superado_oscuro.png`, `celular_aforo_superado_claro.png`, `celular_sin_sesion_claro.png`.

Se abre en el navegador de cualquier celular conectado a la misma red wifi, escribiendo la dirección que muestra el menú (por ejemplo `http://192.168.1.7:8080`; la dirección depende de la red). No requiere instalar nada. Muestra:

- **Encabezado:** logo, nombre del espacio y una pastilla de estado ("En vivo" con punto que parpadea, "Video", "En pausa" o "Sin sesión activa") con el tiempo de la sesión, sobre la red neuronal tenue.
- **Medidor circular:** un anillo que se llena con el porcentaje de ocupación, con el número de personas en el centro. Verde por debajo del 70 %, amarillo desde el 70 % y rojo cuando se supera el aforo.
- **Estado en texto:** "Dentro del aforo", "Cerca del límite", "Aforo completo" o "Aforo superado", con el porcentaje y un ícono de forma distinta para cada nivel (círculo, rombo, triángulo), así el estado no depende solo del color.
- **Tres cifras:** entradas y salidas, cada una con una marca verde o roja como las líneas del video, y cupos libres.
- **Gráfica de la sesión:** la misma curva escalonada del informe, que se actualiza en vivo. Al tocarla muestra cuántas personas había en ese momento.

Se actualiza sola cada segundo, se adapta al tema claro u oscuro del teléfono (incluida la barra de estado del navegador), no muestra el destello gris al tocar y avisa si pierde la conexión con la Raspberry. Es solo de consulta.

## 3.8 LED de alerta

Un LED conectado al pin GPIO17 parpadea mientras la ocupación está por encima del aforo. No tiene elementos en pantalla. Detalles de conexión en `02_como_funciona.md`, sección 2.11.

## 3.9 Cómo se revisó la interfaz

El 29 de octubre la interfaz se revisó con herramientas de crítica de diseño para agentes de programación (las skills *impeccable*, *design-taste-frontend*, *emil-design-eng* y *mobile-native*, y la skill oficial *frontend-design* de Anthropic). La revisión puntuó la interfaz con las 10 heurísticas de usabilidad de Nielsen (27 de 40, "aceptable") y señaló cinco problemas: esperas sin aviso, nombres largos que se montaban sobre otros textos, opciones que podían empeorar el conteo sin advertirlo, formatos de hora inconsistentes, y cuadros de mensaje sin estilo y validación débil. Todos se corrigieron salvo la advertencia sobre la calidad en cámara, que el autor decidió no agregar. El detector automático de *impeccable* no encontró problemas en la página del celular, ni en el código ni abierta en el navegador.

## 3.10 Qué reemplaza cada cosa

Para ubicar los cambios respecto al libro:

| Antes | Ahora |
|---|---|
| Menú Tkinter de una sola columna, con casillas redondas y color azul | Menú CustomTkinter en dos columnas, botones segmentados redondeados, color amarillo |
| Fondo negro liso | Fondo casi negro con un toque azul y encabezados con una red neuronal estilizada |
| Encabezado y panel dibujados encima del video | Cabecera y panel por fuera del video |
| Letra básica de OpenCV, sin tildes | Nunito Sans, con tildes |
| Etiqueta `ID n` | Etiqueta `PERSON ID n` sobre fondo de color |
| Aviso de aforo en el centro de la imagen | Franja roja en la parte superior del video |
| Cuadros de mensaje grises estándar | Avisos con el estilo de la app y lenguaje sencillo |
| Sin aviso mientras carga el modelo | Carga en segundo plano, cuadro "Preparando el detector" y aviso en el video |
| Cuadro de texto con los totales al terminar | Informe con cifras y gráfica |
| CSV sueltos en la carpeta personal | Carpeta `registros/`, con el nombre del espacio |
| Se abría desde la terminal | Ícono en el escritorio |
| Sin acceso remoto | Página web en la red local |
| Solo aviso en pantalla | Aviso en pantalla, en el celular y con LED |
