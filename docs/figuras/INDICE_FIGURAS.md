# Índice de figuras

Todas las capturas se regeneraron el 29 de octubre de 2026 con el programa tal como quedó (`codigo/motiva_app.py`). Son la salida real de la interfaz, no maquetas.

**Aviso para la tesis:** las imágenes de la ventana de video usan videos de prueba de terceros, y en algunas se ve una marca de agua. Sirven para mostrar la interfaz; para la versión final del libro conviene que el autor tome capturas con material propio (por ejemplo, con la cámara instalada en el sitio).

## Identidad

| Archivo | Qué muestra |
|---|---|
| `icono_motiva.png` | Ícono de la aplicación (256x256 px, esquinas transparentes) |

## Menú de configuración

Capturas de la ventana real (1010x635 px), con los valores de fábrica. La dirección del celular que aparece es de ejemplo.

| Archivo | Qué muestra |
|---|---|
| `menu_camara.png` | Menú con la fuente en Cámara web: el archivo, el intervalo y sus notas aparecen apagados; líneas horizontales, entrada hacia abajo, calidad Rápida |
| `menu_video_lineas_verticales.png` | Menú con la fuente en Video: archivo e intervalo activos; líneas verticales, entrada hacia la izquierda, calidad Precisa |

## Avisos y espera

| Archivo | Qué muestra |
|---|---|
| `aviso_error.png` | Aviso al intentar iniciar con un aforo no válido |
| `dialogo_preparando_detector.png` | Cuadro que aparece si se pulsa INICIAR antes de que el detector esté listo |

## Ventana de monitoreo

Imágenes exactas de lo que el programa muestra en la ventana, guardadas durante sesiones reales sobre videos de prueba.

| Archivo | Qué muestra | Cómo se obtuvo |
|---|---|---|
| `ventana_video_deteccion.png` | Varias personas con su caja y etiqueta `PERSON ID n`, líneas horizontales, contadores y barra de ocupación | Modo video sobre `videon.mp4` (escaleras), intervalo 5, calidad Precisa; la imagen con más personas detectadas |
| `ventana_video_preparando.png` | El aviso "Preparando el detector…" antes de la primera detección | La misma sesión, en sus primeras imágenes |
| `ventana_video_vista_superior.png` | Escena vista desde arriba, el punto de vista para el que está hecho el modelo | Modo video sobre `videoa.mp4` (plaza), intervalo 10 |
| `ventana_video_lineas_verticales.png` | Líneas de conteo verticales | Modo video sobre `videoc.mp4`, intervalo 5 |
| `ventana_video_aforo_superado.png` | Franja roja "AFORO SUPERADO", ocupación en rojo y barra llena | Modo video sobre `videon.mp4` con el aforo puesto en 1 para forzar el aviso; espacio "Biblioteca" |
| `ventana_video_en_pausa.png` | Recuadro "PAUSADO" y estado en pausa en la cabecera | Función de dibujo del programa con el estado de pausa y contadores de ejemplo (9 entradas, 4 salidas); los números no vienen de una sesión |
| `ventana_camara_en_vivo_simulada.png` | Estado "EN VIVO" con punto rojo, como se ve con la cámara | El programa en modo cámara recibiendo `videon.mp4` en tiempo real en lugar de la cámara; calidad Rápida. No es la cámara real |

## Informe de sesión

| Archivo | Qué muestra |
|---|---|
| `ventana_informe.png` | La ventana que se abre al terminar una sesión, con el informe y el botón Cerrar |
| `../ejemplos/motiva_Biblioteca_*.png` | Informe de una sesión en la que se superó el aforo (tramos sombreados en rojo). Corresponde al CSV del mismo nombre |
| `../ejemplos/motiva_Salon_E3T_*.png` | Informe de una sesión sin superar el aforo. Corresponde al CSV del mismo nombre |

Los dos ejemplos son sesiones en modo video sobre videos de prueba (`videon.mp4` con aforo 1 y `videoa.mp4` con aforo 20).

## Página para el celular

Capturas tomadas con un navegador en tamaño de teléfono (390 px de ancho). **Los datos son de sesiones inventadas** para mostrar cada estado del diseño; no son conteos reales.

| Archivo | Qué muestra |
|---|---|
| `celular_aforo_completo_oscuro.png` | Ocupación igual al aforo (anillo amarillo, "Aforo completo · 100 %"), tema oscuro |
| `celular_aforo_superado_oscuro.png` | Aforo superado (anillo rojo), tema oscuro |
| `celular_aforo_superado_claro.png` | Aforo superado, tema claro |
| `celular_sin_sesion_claro.png` | Sin sesión activa y sin conteos, tema claro |
