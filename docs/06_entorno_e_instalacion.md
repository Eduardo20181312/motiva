# 6. Entorno, archivos e instalación

## 6.1 Hardware

| Elemento | Detalle |
|---|---|
| Computador | Raspberry Pi 4 Model B Rev 1.5, 4 GB de RAM |
| Almacenamiento | Tarjeta microSD de 32 GB (28 GB útiles) |
| Cámara | Cámara web USB, identificada por el sistema como "DV20 USB"; hasta 1920x1080 a 30 fps |
| Pantalla | Monitor LG W1642 de 1360x768 (hasta mediados de octubre se usó uno de 1920x1080) |
| Alerta | LED con resistencia de 220 a 330 Ω entre el pin físico 11 (GPIO17) y el pin físico 9 (tierra). Previsto; aún no se ha conectado uno |

No hay acelerador de inferencia: el modelo corre en la CPU (4 núcleos Cortex-A72).

## 6.2 Software

| Componente | Versión |
|---|---|
| Sistema operativo | Raspberry Pi OS basado en Debian GNU/Linux 13 (trixie), 64 bits, núcleo 6.18.50 |
| Escritorio | Wayland con el compositor labwc |
| Python | 3.13.5, en un entorno virtual llamado `motiva_env` |
| ultralytics | 8.4.174 |
| openvino | 2026.4.1 |
| opencv-python | 5.0.0.93 |
| torch | 2.14.1 (solo CPU) |
| onnxruntime | 1.30.0 (ya no se usa en ejecución; queda como respaldo) |
| numpy | 2.5.3 |
| pillow | 12.3.0 |
| customtkinter | 6.0.0 (menú, informe y avisos) |
| darkdetect | 0.8.0 (la usa CustomTkinter) |
| gpiod | 2.5.0 |
| lap | 0.5.13 (lo usa el seguidor) |

La lista completa de paquetes está en `codigo/requirements_motiva_env.txt`.

Librerías estándar de Python que usa el programa: `tkinter` (menú e informe), `http.server` y `socket` (página web), `threading`, `queue`, `json`, `csv`.

Nota sobre el LED: se intentó usar `gpiozero` con `lgpio`, que es lo habitual en Raspberry, pero `lgpio` no compiló en este entorno. Se usó `gpiod`, que controla los pines a través de `/dev/gpiochip0`.

## 6.3 El modelo y su historia

Esta parte es delicada para la tesis; léela completa.

- El modelo es un **YOLO11s de una sola clase (`person`)**, entrenado por el autor en Google Colab.
- En la Raspberry hay dos archivos originales del autor que **no son el mismo entrenamiento**:
  - `best.pt`, de un entrenamiento de **abril de 2026**;
  - `best.onnx`, exportado en Colab el **24 de junio de 2026**, de un entrenamiento posterior.
- El sistema **siempre usó los pesos de junio** (`best.onnx`). El archivo `.pt` de junio no está en la Raspberry.
- El 10 de octubre de 2026 los pesos de junio se recuperaron a partir de los tensores de `best.onnx` y se guardaron como `modelos/best_junio.pt`; se verificó que reproducen la salida de `best.onnx` con diferencia 0,0.
- De `best_junio.pt` salieron `modelos/best_dinamico.onnx` (entrada de tamaño variable, usado el 10 y parte del 12 de octubre) y `modelos/best_junio_openvino_model` (formato OpenVINO con entrada variable, **el que usa el sistema ahora**).

Cadena completa: entrenamiento de junio → `best.onnx` → `best_junio.pt` (recuperado) → `best_junio_openvino_model`.

**Datos del entrenamiento de abril**, tal como quedaron guardados dentro de `best.pt`. Sirven como referencia del procedimiento, pero **no son las métricas del modelo en uso**:

| Dato | Valor |
|---|---|
| Modelo base | `yolo11s.pt` |
| Dataset | `/content/person-2/data.yaml` |
| Épocas | 50 |
| Tamaño de imagen | 640 |
| Lote | 16 |
| Duración del entrenamiento | 1035 s (unos 17 minutos) |
| Fecha | 22 de abril de 2026 |
| Precisión | 0,904 |
| Exhaustividad (recall) | 0,911 |
| mAP50 | 0,937 |
| mAP50-95 | 0,558 |

Las métricas del entrenamiento de junio debe aportarlas el autor.

Los archivos de pesos no están en esta carpeta porque pesan unos 38 MB cada uno y no hacen falta para escribir. `codigo/metadata_modelo_openvino.yaml` es la ficha del modelo exportado.

## 6.4 Archivos del sistema en la Raspberry

Todo está en `/home/motivaa/`.

| Ruta | Qué es |
|---|---|
| `motiva_app.py` | El programa |
| `motiva_env/` | Entorno virtual de Python |
| `modelos/best_junio_openvino_model/` | Modelo en uso |
| `modelos/best_dinamico.onnx` | Mismo modelo en ONNX (respaldo) |
| `modelos/best_junio.pt` | Pesos de junio recuperados; de aquí se exporta |
| `modelos/tracker_motiva.yaml` | Configuración de ByteTrack |
| `motiva_config.json` | Configuración recordada (se crea sola) |
| `motiva_icono.png` | Ícono de la aplicación |
| `Desktop/MOTIVA.desktop` | Acceso directo del escritorio |
| `registros/` | Un CSV y un PNG por sesión con conteos |
| `motiva_app_menu_anterior.py` | Copia del programa antes del rediseño de la interfaz del 12 de octubre |
| `motiva_app_antes_customtkinter.py` | Copia del programa antes del cambio a CustomTkinter del 29 de octubre |

## 6.5 Cómo se ejecuta

Normalmente, con doble clic en el ícono MOTIVA del escritorio. El acceso directo ejecuta:

```
/home/motivaa/motiva_env/bin/python /home/motivaa/motiva_app.py
```

Desde una terminal:

```bash
source /home/motivaa/motiva_env/bin/activate
python3 /home/motivaa/motiva_app.py
```

El programa abre ventanas, así que necesita el escritorio de la Raspberry.

## 6.6 Cómo se instaló lo nuevo

Sobre el entorno que ya tenía el autor (ultralytics y OpenCV), el 12 de octubre se instaló con pip, dentro de `motiva_env`:

```bash
pip install openvino    # motor de inferencia
pip install gpiod       # control del pin del LED
pip install customtkinter   # controles modernos del menú (29 de octubre)
```

Y el modelo se exportó a OpenVINO con ultralytics:

```python
from ultralytics import YOLO
YOLO("/home/motivaa/modelos/best_junio.pt").export(format="openvino", dynamic=True, imgsz=640)
```

Advertencia práctica que vale para un anexo: la Raspberry de 4 GB se queda sin memoria si se exporta o se mide un modelo con el editor, el navegador y la aplicación abiertos a la vez. El 10 de octubre una exportación agotó la RAM y el intercambio, y el equipo se reinició.

## 6.7 Formato de los archivos que produce

**CSV de sesión** (`registros/motiva_<espacio>_<AAAAMMDD_HHMMSS>.csv`):

```
Tiempo,Entradas,Salidas,Ocupacion
18:16:41,1,0,1
18:16:41,2,0,2
18:16:42,3,0,3
```

Una fila por cada conteo, con la hora del reloj y los totales acumulados después de ese conteo.

**Informe** (`registros/motiva_<espacio>_<AAAAMMDD_HHMMSS>.png`): imagen de 960x600 px.

**Configuración** (`motiva_config.json`): ver `codigo/ejemplo_motiva_config.json`. Las líneas se guardan como fracción (de 0 a 1) del alto o del ancho de la imagen.

**Estado para la página web** (`http://<IP>:8080/estado`), ejemplo:

```json
{"espacio": "Salon E3T", "activo": true, "pausado": false, "fuente": "camara",
 "entradas": 16, "salidas": 3, "ocupacion": 13, "aforo": 20, "superado": false,
 "segundos": 754, "maximo": 14, "t_maximo": 512.3,
 "curva": [[12.4, 1], [15.0, 2], [31.7, 1]]}
```

Cada elemento de `curva` es `[segundo de la sesión, ocupación]`.
