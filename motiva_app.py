import cv2
import os
import sys
import re
import json
import time
import csv
import queue
import threading
import functools
import random
import gc
import atexit
import socket
import http.server
import numpy as np
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ============================================================
# VARIABLES GLOBALES
# ============================================================
# Todos los archivos de MOTIVA están junto a este programa (en la Raspberry
# del proyecto, /home/motivaa), así funciona en cualquier carpeta
CARPETA       = os.path.dirname(os.path.abspath(__file__))

# Mismos pesos que best.onnx, pero acepta cualquier tamaño de entrada.
# Formato OpenVINO: detecta igual que el ONNX y es más rápido en la Raspberry
# (para volver al anterior: modelos/best_dinamico.onnx)
MODEL_PATH    = os.path.join(CARPETA, "modelos", "best_junio_openvino_model")

# Tamaño de entrada del modelo (múltiplo de 32, máximo 640):
# menor = detecta más veces por segundo, mayor = ve mejor a personas lejanas.
# Estos son los de cada fuente; en el menú se puede elegir otro (IMGSZ)
IMGSZ_CAMARA  = 320
IMGSZ_VIDEO   = 640
IMGSZ         = None   # el elegido en el menú; None = el de la fuente

# Los videos más grandes que esto se achican al leerlos (lado mayor, en pixeles)
LADO_MAX_VIDEO = 960

# Seguimiento: ByteTrack ajustado para pocas detecciones por segundo (el de
# ultralytics por defecto pierde a las personas cuando se detecta poco)
TRACKER       = os.path.join(CARPETA, "modelos", "tracker_motiva.yaml")

# Aspecto (menú y ventana de video)
C_FONDO   = "#11131c"   # con un toque azul, que combina con la red del encabezado
C_TARJETA = "#1e2127"
C_BORDE   = "#2e333d"
C_CAMPO   = "#272b33"
C_TEXTO   = "#e8eaed"
C_SUAVE   = "#8b93a1"
C_APAGADO = "#555b66"
C_ACENTO  = "#ffc800"
C_ACENTO2 = "#ffd84d"   # el acento con el mouse encima
C_VERDE   = "#3ddc64"
C_ROJO    = "#f04a4a"
C_NARANJA = "#ff9a2e"
# Gráfica del informe: azul para la curva y rojo solo para "aforo superado".
# El par se distingue bien sobre el fondo oscuro, también con daltonismo
C_SERIE   = "#3987e3"
C_CRITICO = "#d03b3b"
LETRA     = "Nunito Sans"
LETRA_TTF = ("/usr/share/fonts/truetype/nunito-sans/"
             "NunitoSans-VariableFont_YTLC,opsz,wdth,wght.ttf")
ICONO     = os.path.join(CARPETA, "motiva_icono.png")

# Ventana de video: la cabecera va encima del video y el panel debajo
ALTO_CABECERA = 56
ALTO_PANEL    = 108
PANTALLA      = None   # (ancho, alto) de la pantalla; lo pone el menú

# El modelo se prepara en segundo plano mientras el menú está abierto: cargar
# la librería y hacer la primera detección tarda unos 15 s en la Raspberry
modelo_previo = None   # modelo cargado y probado, listo para la próxima sesión
hilo_modelo   = None
error_modelo  = None

# Estado del sistema
pausado       = False
corriendo     = False
cap           = None
model         = None
lector        = None   # hilo que lee la cámara o el video
detector      = None   # hilo que ejecuta el modelo

# Conteo
entradas      = 0
salidas       = 0
frame_count   = 0
n_inferencias = 0
last_results  = None
inicio        = None
t_sesion      = 0.0   # segundos de sesión (en video: segundos del video)
historial     = []    # (t_sesion, entradas, salidas) de cada conteo
zona_anterior = {}
ultima_pos    = {}   # tid -> (cx, cy, inferencia en que se vio por ultima vez)

# Reasignacion de IDs: si el tracker pierde a una persona y le da un ID
# nuevo, el ID nuevo hereda la zona del ID perdido mas cercano
REASIG_DIST_PCT   = 0.15   # distancia maxima, como fraccion del alto del frame
REASIG_INFERENCIAS = 3     # cuantas inferencias puede llevar perdido el ID viejo

# Adelanto de las cajas en vivo: la detección corresponde a una imagen de
# hace un momento, así que la caja se dibuja donde la persona debería ir ya
pos_deteccion = {}   # tid -> (cx, cy, hora de la imagen detectada)
velocidad     = {}   # tid -> (vx, vy) en pixeles por segundo
ADELANTO_MAX  = 1.0  # segundos; con 0 las cajas se dibujan sin adelantar

# Objetos quietos: el modelo a veces marca como persona un bolso o un montón
# de ropa. Una caja solo vale como persona (se dibuja y se cuenta) cuando se
# ha desplazado desde su ancla, y deja de valer si luego pasa mucho tiempo
# sin moverse; lo que nunca se mueve se ignora. Solo se aplica con la cámara
ancla         = {}     # tid -> (cx, cy, hora, lado mayor) de su último movimiento
confirmados   = set()  # IDs que valen como persona
MOVIMIENTO_MIN = 0.3   # cuánto debe moverse, como fracción del lado mayor
                       # de su caja; con 0 no se filtra nada
TAMANO_MIN    = 0.35   # o cuánto debe cambiar de tamaño (se acerca o se aleja)
QUIETO_MAX    = 10     # segundos sin moverse para dejar de valer

# Líneas
linea_verde       = 200
linea_roja        = 400
arrastrando_verde = False
arrastrando_roja  = False
MARGEN            = 15

# Config
AFORO_MAX     = 20
NOMBRE_ESPACIO = "Espacio MOTIVA"
FUENTE        = 0
INTERVAL      = 5
ORIENTACION   = "horizontal"   # "horizontal" o "vertical"
# Sentido de entrada. False: hacia abajo (o hacia la derecha con líneas
# verticales), la verde queda primero. True: al revés, la verde queda de
# última. La regla no cambia: de la verde hacia la roja = entrada
INVERTIDO     = False

# CSV: uno por sesión, en la carpeta de registros
CARPETA_REGISTROS = os.path.join(CARPETA, "registros")
nombre_csv    = None
archivo_csv   = None
escritor      = None

# Alerta física: LED que parpadea mientras el aforo está superado
PIN_LED       = 17     # GPIO17 (pin físico 11; tierra en el 9). None = sin LED
led           = None

# Página para ver la ocupación desde un celular en la misma red
PUERTO_WEB    = 8080   # None = sin página
URL_WEB       = None   # dirección de la página, cuando está funcionando

# Lo que la app recuerda de la última sesión (opciones del menú y líneas)
ARCHIVO_CONFIG = os.path.join(CARPETA, "motiva_config.json")
CONFIG        = {}

# ============================================================
# FUNCIONES: MODELO PRECARGADO
# ============================================================
def _cargar_modelo():
    global modelo_previo, error_modelo
    try:
        from ultralytics import YOLO
        m = YOLO(MODEL_PATH, task="detect")
        # La primera detección es la lenta: se hace aquí, con una imagen vacía
        m.predict(np.zeros((480, 640, 3), np.uint8), imgsz=IMGSZ_CAMARA,
                  rect=True, verbose=False)
        modelo_previo, error_modelo = m, None
    except Exception as e:
        error_modelo = e

def precargar_modelo():
    # Empieza a preparar un modelo nuevo, salvo que ya haya uno listo o en camino
    global hilo_modelo
    if modelo_previo is not None or (hilo_modelo is not None
                                     and hilo_modelo.is_alive()):
        return
    hilo_modelo = threading.Thread(target=_cargar_modelo, daemon=True)
    hilo_modelo.start()

def tomar_modelo():
    # El modelo precargado, esperándolo si aún no termina. Cada sesión usa
    # uno nuevo, así el seguimiento empieza siempre desde cero
    global modelo_previo
    precargar_modelo()
    hilo_modelo.join()
    m, modelo_previo = modelo_previo, None
    if m is None:
        raise RuntimeError(f"No se pudo cargar el modelo de detección: {error_modelo}")
    return m

# ============================================================
# FUNCIONES: CONFIGURACIÓN RECORDADA
# ============================================================
def cargar_config():
    global CONFIG
    try:
        with open(ARCHIVO_CONFIG, encoding="utf-8") as f:
            datos = json.load(f)
        CONFIG = datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        CONFIG = {}   # primera vez o archivo dañado: se usan los de fábrica

def guardar_config():
    # Se escribe aparte y se reemplaza, para no dañar el archivo si la
    # Raspberry se apaga justo en ese momento
    try:
        temporal = ARCHIVO_CONFIG + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, indent=2, ensure_ascii=False)
        os.replace(temporal, ARCHIVO_CONFIG)
    except OSError:
        pass   # la app sigue funcionando, solo no recuerda

def lineas_recordadas(fuente, largo):
    # Posiciones (menor, mayor) en pixeles de la última sesión con esa
    # fuente y esta orientación, o None si no hay o no sirven
    try:
        a, b = sorted(CONFIG["lineas"][fuente][ORIENTACION])
        menor, mayor = round(a * largo), round(b * largo)
    except (KeyError, TypeError, ValueError):
        return None
    if 0 <= menor and mayor <= largo and mayor - menor >= 30:
        return menor, mayor
    return None

def recordar_lineas(fuente, largo):
    # Se guardan como fracción del video, para que sirvan con otro tamaño
    if not isinstance(CONFIG.get("lineas"), dict):
        CONFIG["lineas"] = {}
    if not isinstance(CONFIG["lineas"].get(fuente), dict):
        CONFIG["lineas"][fuente] = {}
    CONFIG["lineas"][fuente][ORIENTACION] = sorted(
        [round(linea_verde / largo, 6), round(linea_roja / largo, 6)])
    guardar_config()

# ============================================================
# FUNCIÓN: ZONA
# ============================================================
def get_zona(cx, cy):
    # Con líneas verticales se usa la posición horizontal:
    # "arriba" = izquierda de la verde, "abajo" = derecha de la roja
    pos = cx if ORIENTACION == "vertical" else cy
    if INVERTIDO:
        # La verde está después de la roja: "arriba" = pasada la verde
        if pos > linea_verde:
            return "arriba"
        elif pos > linea_roja:
            return "medio"
        else:
            return "abajo"
    if pos < linea_verde:
        return "arriba"
    elif pos < linea_roja:
        return "medio"
    else:
        return "abajo"

# ============================================================
# FUNCIONES: TEXTO Y PIEZAS DE LA VENTANA DE VIDEO
# ============================================================
def bgr(color):
    # "#rrggbb" del menú -> (b, g, r) de OpenCV
    return tuple(int(color[i:i + 2], 16) for i in (5, 3, 1))

@functools.lru_cache(maxsize=None)
def cargar_letra(tam, negrita):
    try:
        letra = ImageFont.truetype(LETRA_TTF, tam)
        # Ejes de Nunito Sans: grosor, ancho, tamaño óptico, YTLC
        letra.set_variation_by_axes([750 if negrita else 500, 100, 12, 500])
        return letra
    except OSError:
        pass
    try:
        return ImageFont.truetype(
            "DejaVuSans-Bold.ttf" if negrita else "DejaVuSans.ttf", tam)
    except OSError:
        return ImageFont.load_default(tam)

@functools.lru_cache(maxsize=1024)
def mascara_texto(texto, tam, negrita):
    # El texto dibujado una sola vez, como máscara de 0 a 255.
    # La letra pequeña se dibuja al doble y se achica: dibujada directo
    # quedan huecos disparejos entre las letras
    doble = 2 if tam <= 16 else 1
    letra = cargar_letra(tam * doble, negrita)
    sube, baja = letra.getmetrics()
    img = Image.new("L", (int(letra.getlength(texto)) + 2 * doble,
                          sube + baja + (sube + baja) % doble), 0)
    ImageDraw.Draw(img).text((0, 0), texto, font=letra, fill=255)
    m = np.asarray(img)
    if doble > 1:
        m = cv2.resize(m, (m.shape[1] // doble, m.shape[0] // doble),
                       interpolation=cv2.INTER_AREA)
    return m.astype(np.uint16)[..., None]

def poner_texto(img, texto, x, y, tam, color, negrita=False, ancla="izq"):
    # Escribe con la letra del menú. (x, y) es la esquina de arriba; con
    # ancla "der" o "centro" el texto se acomoda respecto a x.
    # Devuelve el ancho del texto
    m = mascara_texto(texto, tam, negrita)
    alto, ancho = m.shape[:2]
    if ancla == "der":
        x -= ancho
    elif ancla == "centro":
        x -= ancho // 2
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + ancho, img.shape[1]), min(y + alto, img.shape[0])
    if x0 < x1 and y0 < y1:
        a   = m[y0 - y:y1 - y, x0 - x:x1 - x]
        roi = img[y0:y1, x0:x1]
        roi[:] = (roi * (255 - a) + np.array(color, np.uint16) * a) // 255
    return ancho

def ancho_texto(texto, tam, negrita=False):
    return mascara_texto(texto, tam, negrita).shape[1]

def recortar(texto, tam, ancho_max, negrita=False):
    # El texto tal cual si cabe; si no, cortado con "…" al ancho disponible
    if ancho_texto(texto, tam, negrita) <= ancho_max:
        return texto
    while texto and ancho_texto(texto.rstrip() + "…", tam, negrita) > ancho_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"

def poner_chapa(img, texto, x, y, fondo, tam=11, color=(20, 20, 20)):
    # Texto sobre un rectángulo de color; (x, y) es su esquina de arriba
    ancho = ancho_texto(texto, tam, True) + 12
    alto  = tam + 9
    x = max(0, min(x, img.shape[1] - ancho))
    y = max(0, min(y, img.shape[0] - alto))
    cv2.rectangle(img, (x, y), (x + ancho, y + alto), fondo, -1)
    poner_texto(img, texto, x + 6, y + 2, tam, color, True)

def oscurecer(img, x0, y0, x1, y1, color, fuerza):
    # Tiñe solo ese rectángulo, sin copiar la imagen entera
    x0, y0 = max(x0, 0), max(y0, 0)
    roi = img[y0:y1, x0:x1]
    if roi.size:
        tinte = np.full_like(roi, color)
        cv2.addWeighted(tinte, fuerza, roi, 1 - fuerza, 0, roi)

@functools.lru_cache(maxsize=None)
def cargar_logo(lado):
    logo = cv2.imread(ICONO, cv2.IMREAD_UNCHANGED)
    if logo is None or logo.ndim != 3 or logo.shape[2] != 4:
        return None
    logo = cv2.resize(logo, (lado, lado), interpolation=cv2.INTER_AREA)
    return logo[..., :3].astype(np.uint16), logo[..., 3:].astype(np.uint16)

# Los colores del menú, en el orden de OpenCV
V_FONDO, V_BORDE, V_CAMPO = bgr(C_FONDO), bgr(C_BORDE), bgr(C_CAMPO)
V_TEXTO, V_SUAVE, V_APAGADO = bgr(C_TEXTO), bgr(C_SUAVE), bgr(C_APAGADO)
V_ACENTO, V_VERDE, V_ROJO = bgr(C_ACENTO), bgr(C_VERDE), bgr(C_ROJO)
V_NARANJA = bgr(C_NARANJA)
V_TARJETA, V_SERIE, V_CRITICO = bgr(C_TARJETA), bgr(C_SERIE), bgr(C_CRITICO)

# ============================================================
# FUNCIONES: FONDO DE RED NEURONAL (encabezados)
# ============================================================
# Un mismo dibujo de nodos y conexiones decora el menú, la cabecera del video,
# el informe y la página del celular. Sale siempre igual (semilla fija)
def red_neuronal(ancho, alto, semilla=7):
    # Nodos (x, y, resaltado) y enlaces (punto, punto, resaltado), en pixeles.
    # Un recorrido de un nodo por columna queda resaltado en amarillo
    rnd = random.Random(semilla)
    k = alto / 112
    columnas = []
    for x in np.linspace(ancho * 0.36, ancho * 0.97, 7):
        n = rnd.choice([3, 4, 5, 6])
        ys = np.linspace(alto * 0.16, alto * 0.84, n) + rnd.uniform(-6, 6) * k
        columnas.append([(x + rnd.uniform(-8, 8) * k, y) for y in ys])
    camino = [rnd.randrange(len(c)) for c in columnas]
    enlaces = []
    for i in range(len(columnas) - 1):
        for a, pa in enumerate(columnas[i]):
            for b, pb in enumerate(columnas[i + 1]):
                resaltado = camino[i] == a and camino[i + 1] == b
                if resaltado or rnd.random() < 0.55:
                    enlaces.append((pa, pb, resaltado))
    nodos = [(x, y, camino[i] == a)
             for i, col in enumerate(columnas) for a, (x, y) in enumerate(col)]
    return nodos, enlaces

@functools.lru_cache(maxsize=8)
def capa_red(ancho, alto, desde=0.30, hasta=0.62, fuerza=1.0, corte=None):
    # La red como imagen RGBA: aparece de izquierda a derecha entre `desde` y
    # `hasta` (fracciones del ancho), se apaga abajo y, con `corte` (pixeles
    # desde la derecha), también antes del borde derecho
    SS = 2   # se dibuja al doble y se reduce, para bordes suaves
    W, H = ancho * SS, alto * SS
    k = max(alto / 112, 0.5) * SS
    nodos, enlaces = red_neuronal(W, H)
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    brillo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, g = ImageDraw.Draw(capa), ImageDraw.Draw(brillo)
    acento, azul, nodo = (255, 200, 0), (57, 135, 227), (90, 162, 239)
    for pa, pb, resaltado in enlaces:
        if resaltado:
            g.line((pa, pb), fill=acento + (150,), width=int(6 * k))
            d.line((pa, pb), fill=acento + (230,), width=max(int(2 * k), 1))
        else:
            d.line((pa, pb), fill=azul + (70,), width=max(int(1 * k), 1))
    for x, y, resaltado in nodos:
        r = (5 if resaltado else 4) * k
        c = acento if resaltado else nodo
        g.ellipse((x - 3 * r, y - 3 * r, x + 3 * r, y + 3 * r), fill=c + (110,))
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (255,))
    brillo = brillo.filter(ImageFilter.GaussianBlur(7 * k))
    img = Image.alpha_composite(brillo, capa)
    # Desvanecido: entra por la izquierda, sale por abajo (y por la derecha)
    x = np.linspace(0, 1, W)
    mx = np.clip((x - desde) / (hasta - desde), 0, 1) ** 1.3
    if corte is not None:
        c0, c1 = 1 - (corte + 70) / ancho, 1 - corte / ancho
        mx *= np.clip((c1 - x) / (c1 - c0), 0, 1)
    my = np.ones(H)
    abajo = min(26 * SS, H // 3)
    my[H - abajo:] = np.linspace(1, 0, abajo) ** 1.5
    alfa = np.asarray(img.getchannel("A"), np.float32) * np.outer(my, mx) * fuerza
    img.putalpha(Image.fromarray(alfa.astype(np.uint8)))
    return img.resize((ancho, alto), Image.LANCZOS)

def poner_red(img_bgr, y0, alto, **kw):
    # Mezcla la red sobre una franja de una imagen de OpenCV (BGR)
    franja = img_bgr[y0:y0 + alto]
    capa = np.asarray(capa_red(franja.shape[1], alto, **kw), np.float32)
    a = capa[..., 3:] / 255
    franja[:] = (franja * (1 - a) + capa[..., 2::-1] * a).astype(np.uint8)

def banner_menu(ancho, alto=112):
    # Encabezado del menú: la red, el logo y los títulos en una sola imagen
    img = Image.new("RGBA", (ancho, alto), bgr(C_FONDO)[::-1] + (255,))
    img.alpha_composite(capa_red(ancho, alto))
    try:
        logo = Image.open(ICONO).convert("RGBA").resize((60, 60), Image.LANCZOS)
        img.alpha_composite(logo, (28, 26))
    except OSError:
        pass
    pantalla = np.ascontiguousarray(np.asarray(img.convert("RGB"))[..., ::-1])
    poner_texto(pantalla, "MOTIVA", 104, 22, 30, V_ACENTO, True)
    poner_texto(pantalla, "Sistema de monitoreo de ocupación", 104, 62, 14, V_TEXTO)
    poner_texto(pantalla, "UIS · Ingeniería Electrónica", 104, 84, 12, V_SUAVE)
    return Image.fromarray(pantalla[..., ::-1])

def svg_red(ancho=400, alto=120):
    # La red como SVG para la página del celular; los colores salen del tema
    nodos, enlaces = red_neuronal(ancho, alto)
    partes = []
    for (x1, y1), (x2, y2), resaltado in enlaces:
        partes.append(f'<line class="{"red-camino" if resaltado else "red-enlace"}" '
                      f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for x, y, resaltado in nodos:
        partes.append(f'<circle class="{"red-nodo-camino" if resaltado else "red-nodo"}" '
                      f'cx="{x:.1f}" cy="{y:.1f}" r="{5 if resaltado else 3.6}"/>')
    return (f'<svg class="fondo-red" viewBox="0 0 {ancho} {alto}" '
            f'preserveAspectRatio="xMaxYMid slice" aria-hidden="true">'
            f'<defs><filter id="brillo" x="-50%" y="-50%" width="200%" height="200%">'
            f'<feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/>'
            f'<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'<g filter="url(#brillo)">{"".join(partes)}</g></svg>')

@functools.lru_cache(maxsize=4)
def fondo_cabecera(ancho):
    # Cabecera de la ventana de video con la red, suave y lejos del reloj
    franja = np.full((ALTO_CABECERA, ancho, 3), V_FONDO, np.uint8)
    poner_red(franja, 0, ALTO_CABECERA, desde=0.38, hasta=0.58, fuerza=0.75,
              corte=150)
    return franja

# ============================================================
# FUNCIÓN: DIBUJAR UI
# ============================================================
def dibujar_ui(frame, entradas, salidas, minutos, segundos):
    # Devuelve la imagen completa de la ventana: cabecera, video y panel.
    # El video no queda tapado: la cabecera y el panel van por fuera
    h, w = frame.shape[:2]
    ocupacion = max(0, entradas - salidas)
    superado  = ocupacion > AFORO_MAX

    # ---- Sobre el video: líneas, aviso de aforo y pausa ----
    if ORIENTACION == "vertical":
        cv2.line(frame, (linea_verde, 0), (linea_verde, h), V_VERDE, 2)
        cv2.line(frame, (linea_roja, 0), (linea_roja, h), V_ROJO, 2)
        cy = 42 if superado else 8   # debajo del aviso de aforo
        poner_chapa(frame, "ENTRADA", linea_verde + 6, cy, V_VERDE)
        poner_chapa(frame, "SALIDA", linea_roja + 6, cy, V_ROJO,
                    color=(255, 255, 255))
    else:
        cv2.line(frame, (0, linea_verde), (w, linea_verde), V_VERDE, 2)
        cv2.line(frame, (0, linea_roja), (w, linea_roja), V_ROJO, 2)
        poner_chapa(frame, "ENTRADA", 8, linea_verde - 24, V_VERDE)
        poner_chapa(frame, "SALIDA", 8, linea_roja - 24, V_ROJO,
                    color=(255, 255, 255))

    if superado:
        oscurecer(frame, 0, 0, w, 34, V_ROJO, 0.85)
        poner_texto(frame, "AFORO SUPERADO", w // 2, 7, 15,
                    (255, 255, 255), True, "centro")

    if detector is not None and detector.hechas == 0 and not pausado:
        # La primera detección tarda unos segundos; que se sepa que viene
        texto = "Preparando el detector…"
        ancho = ancho_texto(texto, 14, True) + 32
        oscurecer(frame, (w - ancho) // 2, h - 54, (w + ancho) // 2, h - 20,
                  V_FONDO, 0.8)
        poner_texto(frame, texto, w // 2, h - 47, 14, V_TEXTO, True,
                    "centro")

    if pausado:
        ancho = ancho_texto("PAUSADO", 20, True) + 44
        oscurecer(frame, (w - ancho) // 2, h // 2 - 24,
                  (w + ancho) // 2, h // 2 + 24, V_FONDO, 0.8)
        poner_texto(frame, "PAUSADO", w // 2, h // 2 - 14, 20,
                    V_ACENTO, True, "centro")

    # ---- Lienzo: cabecera + video + panel ----
    lienzo = np.empty((ALTO_CABECERA + h + ALTO_PANEL, w, 3), np.uint8)
    lienzo[:ALTO_CABECERA]      = fondo_cabecera(w)
    lienzo[ALTO_CABECERA + h:]  = V_FONDO
    lienzo[ALTO_CABECERA:ALTO_CABECERA + h] = frame

    # ---- Cabecera ----
    x = 14
    logo = cargar_logo(36)
    if logo is not None:
        color, alfa = logo
        roi = lienzo[10:46, x:x + 36]
        roi[:] = (roi * (255 - alfa) + color * alfa) // 255
        x += 46
    poner_texto(lienzo, "MOTIVA", x, 5, 21, V_ACENTO, True)

    # Tiempo de la sesión y estado, a la derecha
    reloj = hora_corta(minutos * 60 + segundos)
    poner_texto(lienzo, reloj, w - 14, 7, 19, V_TEXTO, True, "der")
    if pausado:
        estado, col_estado = "PAUSADO", V_ACENTO
    elif FUENTE == 0:
        estado, col_estado = "EN VIVO", V_ROJO
    else:
        estado, col_estado = "VIDEO", V_SUAVE

    # El nombre del espacio usa lo que dejan libre el reloj y el estado
    derecha = max(ancho_texto(reloj, 19, True),
                  ancho_texto(estado, 10, True) + 18)
    poner_texto(lienzo, recortar(NOMBRE_ESPACIO, 11, w - 14 - derecha - 20 - x),
                x, 32, 11, V_SUAVE)
    ancho = poner_texto(lienzo, estado, w - 14, 34, 10, col_estado,
                        True, "der")
    if FUENTE == 0 and not pausado:
        cv2.circle(lienzo, (w - 14 - ancho - 9, 42), 4, V_ROJO, -1,
                   cv2.LINE_AA)

    # ---- Panel: los cuatro números ----
    py = ALTO_CABECERA + h
    cv2.line(lienzo, (0, py), (w, py), V_BORDE, 1)
    datos = (("ENTRADAS", entradas, V_VERDE),
             ("SALIDAS", salidas, V_ROJO),
             ("OCUPACIÓN", ocupacion, V_ROJO if superado else V_ACENTO),
             ("AFORO MÁX.", AFORO_MAX, V_TEXTO))
    paso = w / len(datos)
    for i, (nombre, valor, color) in enumerate(datos):
        x = int(i * paso)
        if i:
            cv2.line(lienzo, (x, py + 12), (x, py + 60), V_BORDE, 1)
        poner_texto(lienzo, nombre, x + 14, py + 9, 10, V_SUAVE, True)
        poner_texto(lienzo, str(valor), x + 14, py + 23, 28, color, True)

    # ---- Panel: barra de ocupación ----
    pct = min(ocupacion / AFORO_MAX, 1.0) if AFORO_MAX > 0 else 0
    by  = py + 76
    bx0, bx1 = 18, w - 62
    col_barra = V_VERDE if pct < 0.7 else V_NARANJA if pct < 1.0 else V_ROJO
    cv2.line(lienzo, (bx0, by), (bx1, by), V_CAMPO, 8, cv2.LINE_AA)
    if pct > 0:
        cv2.line(lienzo, (bx0, by), (bx0 + int((bx1 - bx0) * pct), by),
                 col_barra, 8, cv2.LINE_AA)
    poner_texto(lienzo, f"{int(pct * 100)}%", w - 14, by - 9, 12,
                V_TEXTO, True, "der")

    # Instrucciones
    poner_texto(lienzo,
                "Arrastra las líneas  ·  ESPACIO pausa  ·  Q termina",
                14, py + 88, 10, V_SUAVE)
    if URL_WEB is not None and w >= 560:
        poner_texto(lienzo, f"Celular: {URL_WEB[7:]}", w - 14, py + 88, 10,
                    V_SUAVE, ancla="der")

    return lienzo, ocupacion

# ============================================================
# ALERTA FÍSICA: LED DE AFORO SUPERADO
# ============================================================
class LedAlerta:
    # Hace parpadear un LED en segundo plano mientras el aforo está superado
    def __init__(self, pin):
        import gpiod
        from gpiod.line import Direction, Value
        self.pin = pin
        self.ENCENDIDO, self.APAGADO = Value.ACTIVE, Value.INACTIVE
        self.linea = gpiod.request_lines(
            "/dev/gpiochip0", consumer="motiva",
            config={pin: gpiod.LineSettings(direction=Direction.OUTPUT,
                                            output_value=Value.INACTIVE)})
        self.superado = threading.Event()
        self.activo   = True
        self.candado  = threading.Lock()   # el pin se toca de a un hilo
        threading.Thread(target=self._parpadear, daemon=True).start()
        atexit.register(self.cerrar)   # que no quede encendido al salir

    def _parpadear(self):
        while self.activo:
            if self.superado.wait(timeout=0.5):
                self._poner(self.ENCENDIDO)
                time.sleep(0.3)
                self._poner(self.APAGADO)
                time.sleep(0.3)

    def _poner(self, valor):
        with self.candado:
            if self.activo:
                self.linea.set_value(self.pin, valor)

    def alertar(self, superado):
        if superado:
            self.superado.set()
        else:
            self.superado.clear()

    def cerrar(self):
        with self.candado:
            if self.activo:
                self.linea.set_value(self.pin, self.APAGADO)
                self.activo = False
                self.linea.release()

def preparar_led():
    # Deja listo el LED; si no se puede (otro equipo, pin ocupado), la app
    # sigue igual, solo sin la alerta física
    global led
    if led is not None or PIN_LED is None:
        return
    try:
        led = LedAlerta(PIN_LED)
    except Exception as e:
        print(f"Sin LED de alerta: {e}")

# ============================================================
# PÁGINA PARA VER LA OCUPACIÓN DESDE EL CELULAR
# ============================================================
PAGINA_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#11131c">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#eef0f3">
<meta name="color-scheme" content="dark light">
<title>MOTIVA</title>
<style>
  :root {
    color-scheme: dark;
    --fondo: #11131c; --tarjeta: #1e2127; --borde: #2e333d; --rejilla: #2a2f38;
    --texto: #e8eaed; --suave: #8b93a1; --marca: #ffc800; --sombra: none;
    --serie: #3987e3;
    --bien: #0ca30c; --aviso: #fab219; --critico: #d03b3b;
    --linea-entrada: #3ddc64; --linea-salida: #f04a4a;
    --red-enlace: rgba(57, 135, 227, .30); --red-nodo: #5aa2ef; --red-camino: #ffc800;
  }
  @media (prefers-color-scheme: light) {
    :root {
      color-scheme: light;
      --fondo: #eef0f3; --tarjeta: #ffffff; --borde: #e1e4e9; --rejilla: #e6e8ec;
      --texto: #16181d; --suave: #5d6470; --marca: #16181d;
      --sombra: 0 1px 2px rgba(20, 22, 26, .06), 0 6px 18px rgba(20, 22, 26, .06);
      --serie: #2a78d6;
      --red-enlace: rgba(42, 120, 214, .28); --red-nodo: #2a78d6; --red-camino: #d9a400;
    }
  }
  * { box-sizing: border-box; }
  html { -webkit-tap-highlight-color: transparent; -webkit-text-size-adjust: 100%; }
  body {
    margin: 0; padding: 18px 16px 26px; background: var(--fondo); color: var(--texto);
    font-family: "Nunito Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  main { max-width: 440px; margin: 0 auto; }

  header { position: relative; isolation: isolate; display: flex; align-items: center; gap: 12px;
           margin: -18px -16px 16px; padding: 18px 16px 14px; }
  header .logo { flex: none; border-radius: 10px; }
  .fondo-red { position: absolute; inset: 0; width: 100%; height: 100%; z-index: -1; opacity: .6;
               -webkit-mask-image: linear-gradient(to right, transparent 22%, #000 62%);
               mask-image: linear-gradient(to right, transparent 22%, #000 62%); }
  .red-enlace { stroke: var(--red-enlace); stroke-width: 1; }
  .red-camino { stroke: var(--red-camino); stroke-width: 2; }
  .red-nodo { fill: var(--red-nodo); }
  .red-nodo-camino { fill: var(--red-camino); }
  .marca { flex: 1; min-width: 0; }
  h1 { margin: 0; font-size: 20px; line-height: 1.1; letter-spacing: .6px; color: var(--marca); }
  #espacio { font-size: 13px; color: var(--suave); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #sesion {
    flex: none; display: flex; align-items: center; gap: 7px; padding: 6px 11px;
    border: 1px solid var(--borde); border-radius: 999px; background: var(--tarjeta);
    font-size: 12px; font-weight: 600; color: var(--suave);
  }
  #punto { width: 8px; height: 8px; border-radius: 50%; background: var(--suave); }
  #sesion.vivo #punto { background: var(--critico); animation: latir 1.6s ease-in-out infinite; }
  #sesion.vivo { color: var(--texto); }
  @keyframes latir { 50% { opacity: .25; } }

  .tarjeta {
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 16px;
    padding: 16px; box-shadow: var(--sombra);
  }
  .rotulo { font-size: 12px; color: var(--suave); }

  /* Ocupación: medidor circular */
  #bloque { --nivel: var(--bien); padding: 20px 16px 16px; text-align: center; }
  .anillo { position: relative; width: 208px; height: 208px; margin: 0 auto; }
  .anillo svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .anillo circle { fill: none; stroke-width: 14; }
  #pista { stroke: color-mix(in srgb, var(--nivel) 20%, var(--tarjeta)); transition: stroke .4s; }
  #arco { stroke: var(--nivel); stroke-linecap: round; transition: stroke-dashoffset .6s ease, stroke .4s; }
  .centro { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  #ocupacion { font-size: 64px; font-weight: 700; line-height: 1; }
  #de { margin-top: 6px; font-size: 14px; color: var(--suave); }
  #estado {
    display: inline-flex; align-items: center; gap: 8px; margin-top: 14px; padding: 7px 14px;
    border-radius: 999px; font-size: 14px; font-weight: 600;
    background: color-mix(in srgb, var(--nivel) 14%, var(--tarjeta));
  }
  #icono { flex: none; fill: var(--nivel); }
  .cambio { animation: saltar .35s ease; }
  @keyframes saltar { 40% { transform: scale(1.08); } }

  .fila { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
  .fila .tarjeta { padding: 12px 12px 14px; }
  .clave-linea { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin: 0 6px 3px 0; vertical-align: middle; }
  .clave-linea.entrada { background: var(--linea-entrada); }
  .clave-linea.salida { background: var(--linea-salida); }
  .cifra { margin-top: 4px; font-size: 28px; font-weight: 700; line-height: 1.1; }

  /* Gráfica */
  #tendencia { margin-top: 10px; padding-bottom: 12px; }
  .titulo { font-size: 14px; font-weight: 700; }
  #lectura { margin-top: 2px; min-height: 17px; font-size: 12px; color: var(--suave); }
  #lectura b { color: var(--texto); }
  #curva { display: block; width: 100%; height: 150px; margin-top: 8px; touch-action: pan-y; }
  #curva text { font-size: 10px; fill: var(--suave); font-family: inherit; }
  #curva .sobre { paint-order: stroke; stroke: var(--tarjeta); stroke-width: 4px; stroke-linejoin: round; }
  .rejilla { stroke: var(--rejilla); stroke-width: 1; }
  .linea { fill: none; stroke: var(--serie); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
  .area { fill: var(--serie); opacity: .1; }
  .tope { stroke: var(--critico); stroke-width: 1; }
  .mira { stroke: var(--suave); stroke-width: 1; }
  .punto { fill: var(--serie); stroke: var(--tarjeta); stroke-width: 2; }

  footer { margin-top: 16px; text-align: center; font-size: 11px; color: var(--suave); }
  #aviso { display: none; margin-top: 10px; text-align: center; font-size: 13px; color: var(--suave); }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
</head>
<body>
<main>
  <header>
    <!--RED-->
    <svg class="logo" width="40" height="40" viewBox="0 0 256 256" aria-hidden="true">
      <rect width="256" height="256" rx="44" fill="#1a1a1a"/>
      <path d="M58 168V60l70 68 70-68v108" fill="none" stroke="#ffc800" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M40 196h176" stroke="#00ff00" stroke-width="8" stroke-linecap="round"/>
      <path d="M40 220h176" stroke="#ff0000" stroke-width="8" stroke-linecap="round"/>
    </svg>
    <div class="marca"><h1>MOTIVA</h1><div id="espacio">&nbsp;</div></div>
    <div id="sesion"><span id="punto"></span><span id="sesionTexto">Conectando…</span></div>
  </header>

  <section class="tarjeta" id="bloque">
    <div class="anillo">
      <svg viewBox="0 0 208 208" aria-hidden="true">
        <circle id="pista" cx="104" cy="104" r="92"/>
        <circle id="arco" cx="104" cy="104" r="92" stroke-dasharray="578.05" stroke-dashoffset="578.05"/>
      </svg>
      <div class="centro">
        <div class="rotulo">Ocupación</div>
        <div id="ocupacion">–</div>
        <div id="de">&nbsp;</div>
      </div>
    </div>
    <div id="estado"><svg id="icono" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"></svg><span id="texto">&nbsp;</span></div>
  </section>

  <div class="fila">
    <section class="tarjeta"><div class="rotulo"><i class="clave-linea entrada"></i>Entradas</div><div class="cifra" id="entradas">–</div></section>
    <section class="tarjeta"><div class="rotulo"><i class="clave-linea salida"></i>Salidas</div><div class="cifra" id="salidas">–</div></section>
    <section class="tarjeta"><div class="rotulo">Cupos libres</div><div class="cifra" id="libres">–</div></section>
  </div>

  <section class="tarjeta" id="tendencia">
    <div class="titulo">Ocupación durante la sesión</div>
    <div id="lectura">&nbsp;</div>
    <svg id="curva" role="img" aria-label="Ocupación a lo largo de la sesión"></svg>
  </section>

  <div id="aviso">Sin conexión con la Raspberry. Reintentando…</div>
  <footer>UIS · Ingeniería Electrónica</footer>
</main>
<script>
  const el = id => document.getElementById(id);
  const dos = n => String(n).padStart(2, "0");
  // Con `escala` (la duración de la sesión) todas las horas de una misma
  // gráfica salen con el mismo formato
  const reloj = (s, escala) => {
    s = Math.round(s);
    const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
    return (h || (escala || 0) >= 3600 ? h + ":" + dos(m) : dos(m)) + ":" + dos(s % 60);
  };
  const LARGO = 2 * Math.PI * 92;
  // Formas fijas del ícono de estado (no vienen de los datos)
  const ICONOS = {
    circulo:   '<circle cx="7" cy="7" r="5.5"/>',
    triangulo: '<path d="M7 1.5 13 12.5H1Z"/>',
    rombo:     '<path d="M7 1 13 7 7 13 1 7Z"/>'
  };
  let dato = null, tocado = null;   // último estado recibido y segundo señalado en la gráfica

  function poner(id, valor) {
    const e = el(id);
    if (e.textContent !== String(valor)) {
      e.textContent = valor;
      e.classList.remove("cambio"); void e.offsetWidth; e.classList.add("cambio");
    }
  }

  function ocupacionEn(t) {
    let v = 0;
    for (const [tp, o] of dato.curva) { if (tp <= t) v = o; else break; }
    return v;
  }

  function dibujarCurva() {
    const svg = el("curva"), d = dato;
    const W = svg.clientWidth || 320, H = 150, izq = 28, der = 12, arr = 12, aba = 20;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    const dur = Math.max(d.segundos, 1);
    const verAforo = d.aforo <= 3 * Math.max(d.maximo, 1);
    const tope0 = Math.max(d.maximo, verAforo ? d.aforo : 0, 1) * 1.15;
    const paso = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].find(p => tope0 / p <= 3) || 1000;
    const tope = paso * Math.ceil(tope0 / paso);
    const x = t => izq + (W - izq - der) * Math.min(Math.max(t, 0), dur) / dur;
    const y = v => H - aba - (H - arr - aba) * v / tope;
    let s = "";
    for (let v = 0; v <= tope; v += paso)
      s += '<line class="rejilla" x1="' + izq + '" x2="' + (W - der) + '" y1="' + y(v) + '" y2="' + y(v) + '"/>' +
           '<text x="' + (izq - 7) + '" y="' + (y(v) + 3.5) + '" text-anchor="end">' + v + '</text>';
    s += '<text x="' + izq + '" y="' + (H - 4) + '">' + reloj(0, dur) + '</text>' +
         '<text x="' + (W - der) + '" y="' + (H - 4) + '" text-anchor="end">' + reloj(dur, dur) + '</text>';
    let p = "M" + x(0) + "," + y(0), ultimo = 0;
    for (const [t, o] of d.curva) { p += "H" + x(t) + "V" + y(o); ultimo = o; }
    p += "H" + x(dur);
    s += '<path class="area" d="' + p + "V" + y(0) + "H" + x(0) + 'Z"/>';
    if (verAforo)
      s += '<line class="tope" x1="' + izq + '" x2="' + (W - der) + '" y1="' + y(d.aforo) + '" y2="' + y(d.aforo) + '"/>' +
           '<text class="sobre" x="' + (izq + 4) + '" y="' + (y(d.aforo) - 5) + '">Aforo ' + d.aforo + '</text>';
    s += '<path class="linea" d="' + p + '"/>';
    if (tocado !== null) {
      const t = Math.min(tocado, dur);
      s += '<line class="mira" x1="' + x(t) + '" x2="' + x(t) + '" y1="' + arr + '" y2="' + (H - aba) + '"/>' +
           '<circle class="punto" cx="' + x(t) + '" cy="' + y(ocupacionEn(t)) + '" r="5"/>';
    } else {
      s += '<circle class="punto" cx="' + x(dur) + '" cy="' + y(ultimo) + '" r="5"/>';
    }
    svg.innerHTML = s;

    const lectura = el("lectura");
    lectura.textContent = "";
    const fuerte = document.createElement("b");
    if (tocado !== null) {
      const v = ocupacionEn(Math.min(tocado, dur));
      fuerte.textContent = v + (v === 1 ? " persona" : " personas");
      lectura.append(fuerte, " a los " + reloj(Math.min(tocado, dur)));
    } else if (d.curva.length === 0) {
      lectura.textContent = "Todavía no hay conteos en esta sesión";
    } else {
      fuerte.textContent = "Máximo: " + d.maximo;
      lectura.append(fuerte, " a los " + reloj(d.t_maximo) + " · toca la gráfica");
    }
  }

  function senalar(ev) {
    if (!dato) return;
    const svg = el("curva"), r = svg.getBoundingClientRect();
    const dur = Math.max(dato.segundos, 1);
    tocado = Math.min(Math.max((ev.clientX - r.left - 28) / (r.width - 40), 0), 1) * dur;
    dibujarCurva();
  }
  const soltar = () => { tocado = null; if (dato) dibujarCurva(); };
  el("curva").addEventListener("pointerdown", senalar);
  el("curva").addEventListener("pointermove", ev => { if (ev.pointerType === "mouse" || ev.buttons || ev.pressure > 0) senalar(ev); });
  el("curva").addEventListener("pointerleave", soltar);
  el("curva").addEventListener("pointerup", ev => { if (ev.pointerType !== "mouse") soltar(); });
  el("curva").addEventListener("pointercancel", soltar);
  window.addEventListener("resize", () => { if (dato) dibujarCurva(); });

  async function actualizar() {
    try {
      const r = await fetch("/estado", {cache: "no-store"});
      const d = dato = await r.json();
      const pct = d.aforo > 0 ? d.ocupacion / d.aforo : 0;
      let nivel = "bien", icono = ICONOS.circulo, texto = "Dentro del aforo";
      if (d.superado)      { nivel = "critico"; icono = ICONOS.triangulo; texto = "Aforo superado"; }
      else if (pct >= 1)   { nivel = "aviso";   icono = ICONOS.rombo;     texto = "Aforo completo"; }
      else if (pct >= 0.7) { nivel = "aviso";   icono = ICONOS.rombo;     texto = "Cerca del límite"; }
      el("bloque").style.setProperty("--nivel", "var(--" + nivel + ")");
      el("icono").innerHTML = icono;
      el("texto").textContent = texto + " · " + Math.round(pct * 100) + " %";
      el("arco").style.strokeDashoffset = LARGO * (1 - Math.min(pct, 1));
      poner("ocupacion", d.ocupacion);
      el("de").textContent = "de " + d.aforo + (d.aforo === 1 ? " persona" : " personas");
      poner("entradas", d.entradas);
      poner("salidas", d.salidas);
      poner("libres", Math.max(d.aforo - d.ocupacion, 0));
      el("espacio").textContent = d.espacio;
      el("sesion").className = d.activo && !d.pausado ? "vivo" : "";
      el("sesionTexto").textContent = !d.activo ? "Sin sesión activa"
        : d.pausado ? "En pausa · " + reloj(d.segundos)
        : (d.fuente === "camara" ? "En vivo · " : "Video · ") + reloj(d.segundos);
      el("aviso").style.display = "none";
      dibujarCurva();
    } catch (e) {
      el("sesion").className = "";
      el("sesionTexto").textContent = "Sin conexión";
      el("aviso").style.display = "block";
    }
  }
  actualizar();
  setInterval(actualizar, 1000);
</script>
</body>
</html>
"""

# La red del encabezado se dibuja una vez, con el mismo trazo de la app
PAGINA_HTML = PAGINA_HTML.replace("<!--RED-->", svg_red(400, 78))

def estado_actual():
    # Lo que la página consulta cada segundo
    ocupacion = max(0, entradas - salidas)
    curva = [(round(t, 1), max(0, ent - sal)) for t, ent, sal in list(historial)]
    maximo, t_maximo = 0, 0.0
    for t, ocup in curva:
        if ocup > maximo:
            maximo, t_maximo = ocup, t
    if len(curva) > 240:
        # Sesión larga: un punto por tramo de tiempo, con el mayor de cada tramo
        tramo, resumida = max(t_sesion, 1.0) / 240, {}
        for t, ocup in curva:
            i = int(t / tramo)
            if i not in resumida or ocup > resumida[i][1]:
                resumida[i] = (t, ocup)
        curva = sorted(resumida.values()) + [curva[-1]]
    return {"espacio": NOMBRE_ESPACIO, "activo": corriendo,
            "pausado": pausado, "fuente": "camara" if FUENTE == 0 else "video",
            "entradas": entradas, "salidas": salidas,
            "ocupacion": ocupacion, "aforo": AFORO_MAX,
            "superado": ocupacion > AFORO_MAX, "segundos": int(t_sesion),
            "maximo": maximo, "t_maximo": t_maximo, "curva": curva}

class PaginaWeb(http.server.BaseHTTPRequestHandler):
    # Solo entrega la página y los números; no recibe nada
    def do_GET(self):
        if self.path == "/estado":
            cuerpo, tipo = json.dumps(estado_actual()).encode(), "application/json"
        elif self.path in ("/", "/index.html"):
            cuerpo, tipo = PAGINA_HTML.encode(), "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass   # sin llenar la terminal con cada consulta

def iniciar_pagina_web():
    # Arranca la página en segundo plano y guarda su dirección en URL_WEB.
    # Si no se puede (sin red, puerto ocupado), la app sigue sin ella
    global URL_WEB
    if URL_WEB is not None or PUERTO_WEB is None:
        return
    try:
        servidor = http.server.ThreadingHTTPServer(("", PUERTO_WEB), PaginaWeb)
        servidor.daemon_threads = True
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        # La dirección de la Raspberry en la red local (no envía nada)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        URL_WEB = f"http://{s.getsockname()[0]}:{PUERTO_WEB}"
        s.close()
    except OSError as e:
        print(f"Sin página para el celular: {e}")

# ============================================================
# FUNCIONES: INFORME DE LA SESIÓN
# ============================================================
def hora_corta(seg, escala=0):
    # mm:ss, o h:mm:ss desde la primera hora. Con `escala` (la duración de
    # la sesión) todas las horas de una misma gráfica salen con un formato
    seg = int(round(seg))
    if seg >= 3600 or escala >= 3600:
        return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}"
    return f"{seg // 60:02d}:{seg % 60:02d}"

def paso_limpio(maximo, opciones, cuantos):
    # El paso más pequeño de `opciones` que deja como mucho `cuantos` marcas
    for paso in opciones:
        if maximo / paso <= cuantos:
            return paso
    return opciones[-1]

def resumir_sesion(historial, duracion, aforo):
    # historial: [(segundo, entradas, salidas), ...] con cada conteo.
    # Devuelve la curva de ocupación y los datos del informe
    curva = [(0.0, 0)]
    for t, ent, sal in historial:
        curva.append((min(t, duracion), max(0, ent - sal)))
    maximo, t_maximo, superado, tramos = 0, 0.0, 0.0, []
    for i, (t, ocup) in enumerate(curva):
        if ocup > maximo:
            maximo, t_maximo = ocup, t
        fin = curva[i + 1][0] if i + 1 < len(curva) else duracion
        if ocup > aforo and fin > t:
            superado += fin - t
            if tramos and tramos[-1][1] == t:
                tramos[-1] = (tramos[-1][0], fin)   # sigue el mismo tramo
            else:
                tramos.append((t, fin))
    return {"curva": curva, "maximo": maximo, "t_maximo": t_maximo,
            "superado": superado, "tramos": tramos}

def dibujar_informe(historial, duracion, fuente, fecha):
    # Imagen del informe: las cifras de la sesión y la ocupación en el tiempo
    W, H = 960, 600
    duracion = max(duracion, 1.0)
    r     = resumir_sesion(historial, duracion, AFORO_MAX)
    final = r["curva"][-1][1]
    img   = np.full((H, W, 3), V_FONDO, np.uint8)
    poner_red(img, 0, 76, desde=0.48, hasta=0.78, fuerza=0.45)

    # ---- Cabecera ----
    x = 24
    logo = cargar_logo(40)
    if logo is not None:
        color, alfa = logo
        roi = img[20:60, x:x + 40]
        roi[:] = (roi * (255 - alfa) + color * alfa) // 255
        x += 54
    poner_texto(img, "Informe de sesión", x, 14, 22, V_TEXTO, True)
    resto = f"  ·  {fecha}  ·  {fuente}  ·  duración {hora_corta(duracion)}"
    espacio = recortar(NOMBRE_ESPACIO, 12, W - 24 - x - ancho_texto(resto, 12))
    poner_texto(img, espacio + resto, x, 44, 12, V_SUAVE)

    # ---- Cifras ----
    if r["superado"] > 0:
        sobre = hora_corta(r["superado"])
        nota  = f"{100 * r['superado'] / duracion:.0f} % de la sesión"
    else:
        sobre, nota = "Nunca", "no se superó el aforo"
    cifras = (("Entradas", str(historial[-1][1]), "personas"),
              ("Salidas", str(historial[-1][2]), "personas"),
              ("Ocupación final", str(final), f"de {AFORO_MAX} de aforo"),
              ("Ocupación máxima", str(r["maximo"]),
               f"a los {hora_corta(r['t_maximo'])}"),
              ("Sobre el aforo", sobre, nota))
    sep   = 12
    ancho = (W - 48 - sep * (len(cifras) - 1)) // len(cifras)
    for i, (nombre, valor, detalle) in enumerate(cifras):
        x0 = 24 + i * (ancho + sep)
        cv2.rectangle(img, (x0, 84), (x0 + ancho, 176), V_TARJETA, -1)
        cv2.rectangle(img, (x0, 84), (x0 + ancho, 176), V_BORDE, 1)
        tx = x0 + 14
        if i == 4 and r["superado"] > 0:
            # El rojo siempre va con su texto al lado, nunca solo
            cv2.circle(img, (tx + 4, 102), 4, V_CRITICO, -1, cv2.LINE_AA)
            tx += 14
        poner_texto(img, nombre, tx, 94, 11, V_SUAVE)
        poner_texto(img, valor, x0 + 14, 112, 28, V_TEXTO, True)
        poner_texto(img, detalle, x0 + 14, 152, 10, V_SUAVE)

    # ---- Gráfica: ocupación en el tiempo ----
    cv2.rectangle(img, (24, 192), (W - 24, H - 40), V_TARJETA, -1)
    cv2.rectangle(img, (24, 192), (W - 24, H - 40), V_BORDE, 1)
    poner_texto(img, "Ocupación durante la sesión", 40, 202, 14, V_TEXTO, True)

    # El aforo entra en la escala si no aplasta la curva
    ver_aforo = AFORO_MAX <= 3 * max(r["maximo"], 1)
    tope      = max(r["maximo"], AFORO_MAX if ver_aforo else 0, 1)
    paso_y    = paso_limpio(tope * 1.15,
                            (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000), 5)
    tope_y    = paso_y * int(np.ceil(tope * 1.15 / paso_y))
    subtitulo = "Personas dentro del espacio"
    if not ver_aforo:
        subtitulo += f"  ·  el aforo máximo ({AFORO_MAX}) queda por encima de la escala"
    poner_texto(img, subtitulo, 40, 224, 11, V_SUAVE)
    if r["tramos"]:
        ancho_t = ancho_texto("Aforo superado", 11)
        cv2.rectangle(img, (W - 50 - ancho_t - 16, 207),
                      (W - 50 - ancho_t - 6, 217), V_CRITICO, -1)
        poner_texto(img, "Aforo superado", W - 50, 204, 11, V_SUAVE,
                    ancla="der")

    px0, px1, py0, py1 = 76, W - 76, 258, H - 82
    def en_x(t):
        return int(round(px0 + (px1 - px0) * t / duracion))
    def en_y(v):
        return int(round(py1 - (py1 - py0) * v / tope_y))

    # Tramos con el aforo superado: una franja suave detrás de la curva
    for t0, t1 in r["tramos"]:
        oscurecer(img, en_x(t0), py0, max(en_x(t1), en_x(t0) + 2), py1,
                  V_CRITICO, 0.14)

    # Rejilla y ejes: líneas finas y discretas
    v = 0
    while v <= tope_y:
        cv2.line(img, (px0, en_y(v)), (px1, en_y(v)), V_BORDE, 1)
        poner_texto(img, str(v), px0 - 10, en_y(v) - 8, 11, V_SUAVE,
                    ancla="der")
        v += paso_y
    paso_x = paso_limpio(duracion, (5, 10, 15, 30, 60, 120, 300, 600, 900,
                                    1800, 3600, 7200, 14400), 7)
    t = 0
    while t <= duracion:
        cv2.line(img, (en_x(t), py1), (en_x(t), py1 + 4), V_BORDE, 1)
        poner_texto(img, hora_corta(t, duracion), en_x(t), py1 + 9, 11, V_SUAVE,
                    ancla="centro")
        t += paso_x
    poner_texto(img, "Tiempo de la sesión", (px0 + px1) // 2, py1 + 28, 10,
                V_SUAVE, ancla="centro")

    # La curva: escalones, porque la ocupación cambia de golpe con cada conteo
    curva = r["curva"]
    resumida = len(curva) > px1 - px0
    if resumida:
        # Más conteos que pixeles: un escalón por columna, con el último valor
        # de cada una, para que la línea no se vuelva una mancha dentada
        por_columna = {}
        for t, ocup in curva:
            por_columna[en_x(t)] = ocup
        curva = [((xx - px0) * duracion / (px1 - px0), o)
                 for xx, o in sorted(por_columna.items())]
    puntos = []
    for i, (t, ocup) in enumerate(curva):
        if i and not resumida:   # resumida ya no se dibuja en escalones
            puntos.append((en_x(t), en_y(curva[i - 1][1])))
        puntos.append((en_x(t), en_y(ocup)))
    puntos.append((px1, en_y(final)))
    relleno = img.copy()
    cv2.fillPoly(relleno, [np.array(puntos + [(px1, py1), (px0, py1)],
                                    np.int32)], V_SERIE)
    cv2.addWeighted(relleno, 0.10, img, 0.90, 0, img)
    cv2.polylines(img, [np.array(puntos, np.int32)], False, V_SERIE, 2,
                  cv2.LINE_AA)

    # Línea del aforo, con su nombre
    if ver_aforo:
        cv2.line(img, (px0, en_y(AFORO_MAX)), (px1, en_y(AFORO_MAX)),
                 V_CRITICO, 1)
        poner_texto(img, f"Aforo máximo: {AFORO_MAX}", px1,
                    en_y(AFORO_MAX) - 17, 11, V_SUAVE, ancla="der")

    # Solo se rotulan el máximo y el valor final
    if r["maximo"] > 0:
        mx, my = en_x(r["t_maximo"]), en_y(r["maximo"])
        cv2.circle(img, (mx, my), 6, V_TARJETA, -1, cv2.LINE_AA)
        cv2.circle(img, (mx, my), 4, V_SERIE, -1, cv2.LINE_AA)
        rotulo = f"Máximo: {r['maximo']}"
        medio  = ancho_texto(rotulo, 11, True) // 2
        poner_texto(img, rotulo, min(max(mx, px0 + medio), px1 - medio),
                    my - 24, 11, V_TEXTO, True, "centro")
    poner_texto(img, str(final), px1 + 8, en_y(final) - 8, 12, V_TEXTO, True)

    # ---- Pie ----
    poner_texto(img, "Cada conteo de la sesión está en el archivo CSV de "
                     "la carpeta registros, con el mismo nombre.",
                24, H - 28, 10, V_SUAVE)
    return img

def mostrar_informe(ruta):
    # Ventana con la imagen del informe; espera a que la cierren.
    # Devuelve False si no se pudo mostrar
    if tk._default_root is None:
        return False
    try:
        imagen = Image.open(ruta)
    except OSError:
        return False
    v = ctk.CTkToplevel(fg_color=C_FONDO)
    v.title("MOTIVA - Informe de sesión")
    v.resizable(False, False)
    ctk.CTkLabel(v, text="", image=ctk.CTkImage(light_image=imagen,
                                                dark_image=imagen,
                                                size=imagen.size)).pack()

    pie = ctk.CTkFrame(v, fg_color="transparent")
    pie.pack(fill="x", padx=24, pady=(6, 18))
    carpeta, archivo = os.path.split(ruta)
    ctk.CTkLabel(pie, text=f"Guardado en {os.path.basename(carpeta)}/{archivo}",
                 font=letra(12), text_color=C_SUAVE).pack(side="left")
    ctk.CTkButton(pie, text="Cerrar", font=letra(14, True), width=120,
                  height=38, corner_radius=8, fg_color=C_ACENTO,
                  hover_color=C_ACENTO2, text_color="#111111",
                  command=v.destroy).pack(side="right")

    v.bind("<Escape>", lambda e: v.destroy())
    v.bind("<Return>", lambda e: v.destroy())
    centrar(v, 30)
    v.after(50, lambda: (v.lift(), v.focus_force()))
    v.wait_window()
    return True

# ============================================================
# MOUSE
# ============================================================
def mouse_callback(event, x, y, flags, param):
    global linea_verde, linea_roja
    global arrastrando_verde, arrastrando_roja

    # Las líneas verticales se mueven con la posición horizontal del mouse.
    # La cabecera corre el video hacia abajo dentro de la ventana
    pos = x if ORIENTACION == "vertical" else y - ALTO_CABECERA

    if event == cv2.EVENT_LBUTTONDOWN:
        if abs(pos - linea_verde) < MARGEN:
            arrastrando_verde = True
        elif abs(pos - linea_roja) < MARGEN:
            arrastrando_roja = True

    elif event == cv2.EVENT_MOUSEMOVE:
        # Las líneas no se pueden cruzar entre sí
        if arrastrando_verde:
            linea_verde = (max(pos, linea_roja + 30) if INVERTIDO
                           else min(pos, linea_roja - 30))
        elif arrastrando_roja:
            linea_roja = (min(pos, linea_verde - 30) if INVERTIDO
                          else max(pos, linea_verde + 30))

    elif event == cv2.EVENT_LBUTTONUP:
        arrastrando_verde = False
        arrastrando_roja  = False

# ============================================================
# FUNCIÓN: REGISTRAR EVENTO EN CSV
# ============================================================
def registrar_evento():
    global archivo_csv, escritor
    # El archivo se crea con el primer conteo: una sesión sin conteos
    # no deja un archivo vacío
    if archivo_csv is None:
        os.makedirs(CARPETA_REGISTROS, exist_ok=True)
        archivo_csv = open(nombre_csv, 'w', newline='')
        escritor    = csv.writer(archivo_csv)
        escritor.writerow(["Tiempo", "Entradas", "Salidas", "Ocupacion"])
    historial.append((t_sesion, entradas, salidas))
    escritor.writerow([
        time.strftime('%H:%M:%S'),
        entradas, salidas,
        max(0, entradas - salidas)
    ])
    archivo_csv.flush()  # Guardar ya, por si el programa se cierra mal

# ============================================================
# FUNCIÓN: DETECTAR Y SEGUIR PERSONAS
# ============================================================
def detectar(frame, imgsz):
    # rect=True ajusta la entrada a la forma de la imagen, sin relleno inútil
    return model.track(
        source=frame,
        persist=True,
        imgsz=imgsz,
        rect=True,
        tracker=TRACKER,
        conf=0.30,
        iou=0.35,
        classes=[0],
        verbose=False
    )

# ============================================================
# FUNCIÓN: VELOCIDAD DE CADA PERSONA (para adelantar las cajas en vivo)
# ============================================================
def actualizar_velocidades(result, t):
    global pos_deteccion, velocidad
    posiciones, velocidades = {}, {}
    boxes = result.boxes
    if boxes is not None and boxes.id is not None:
        for box, track_id in zip(boxes.xyxy, boxes.id):
            x1, y1, x2, y2 = box.tolist()
            tid = int(track_id)
            cx  = (x1 + x2) / 2
            cy  = (y1 + y2) / 2
            posiciones[tid] = (cx, cy, t)
            if tid in pos_deteccion:
                ox, oy, ot = pos_deteccion[tid]
                if t > ot:
                    vx = (cx - ox) / (t - ot)
                    vy = (cy - oy) / (t - ot)
                    # Suavizar con la velocidad anterior para que no tiemble
                    if tid in velocidad:
                        vx = 0.7 * vx + 0.3 * velocidad[tid][0]
                        vy = 0.7 * vy + 0.3 * velocidad[tid][1]
                    velocidades[tid] = (vx, vy)
    pos_deteccion, velocidad = posiciones, velocidades

# ============================================================
# FUNCIÓN: ACHICAR VIDEOS GRANDES
# ============================================================
def reducir(frame):
    # El modelo trabaja a 640 como máximo, y dibujar sobre frames
    # enormes frena la reproducción
    h, w = frame.shape[:2]
    mayor = max(h, w)
    if mayor <= LADO_MAX_VIDEO:
        return frame
    escala = LADO_MAX_VIDEO / mayor
    return cv2.resize(frame, (round(w * escala), round(h * escala)),
                      interpolation=cv2.INTER_AREA)

# ============================================================
# HILOS DE LECTURA Y DETECCIÓN
# ============================================================
class LectorCamara:
    # Lee la cámara sin parar y guarda solo el frame más reciente,
    # para que nunca se muestren imágenes atrasadas
    def __init__(self, cap):
        self.cap       = cap
        self.frame     = None
        self.numero    = 0
        self.visto_det = 0
        self.activo    = True
        self.cond      = threading.Condition()
        self.hilo      = threading.Thread(target=self._leer, daemon=True)
        self.hilo.start()

    def _leer(self):
        while self.activo:
            ret, frame = self.cap.read()
            with self.cond:
                if ret:
                    self.frame   = frame
                    self.numero += 1
                else:
                    self.activo = False
                self.cond.notify_all()

    def leer(self, visto):
        # Espera un frame más nuevo que el número `visto`.
        # Devuelve (numero, frame); frame es None si la cámara dejó de responder
        with self.cond:
            llego = self.cond.wait_for(
                lambda: self.numero > visto or not self.activo, timeout=3)
            if not llego or not self.activo:
                return visto, None
            return self.numero, self.frame

    def para_detectar(self):
        # (frame más reciente, su hora) para el detector; None = terminar
        while True:
            self.visto_det, frame = self.leer(self.visto_det)
            if frame is None:
                return None
            if not pausado:
                return frame, time.time()

    def detener(self):
        self.activo = False
        self.hilo.join(timeout=2)


class LectorVideo:
    # Lee el video por adelantado y aparta 1 de cada INTERVAL frames para el
    # detector, así el resultado ya está listo cuando a ese frame le toca mostrarse
    def __init__(self, cap, fps):
        self.cap      = cap
        self.fps      = fps
        self.activo   = True
        self.frames   = queue.Queue(maxsize=2 * INTERVAL)
        self.muestras = queue.Queue(maxsize=2)
        self.hilo     = threading.Thread(target=self._leer, daemon=True)
        self.hilo.start()

    def _leer(self):
        numero = 0
        while self.activo:
            ret, frame = self.cap.read()
            if not ret:
                break
            numero += 1
            frame = reducir(frame)
            if numero % INTERVAL == 0:
                self._poner(self.muestras, (frame.copy(), numero / self.fps))
            self._poner(self.frames, frame)
        self._poner(self.frames, None)
        self._poner(self.muestras, None)

    def _poner(self, cola, dato):
        while self.activo:
            try:
                cola.put(dato, timeout=0.2)
                return
            except queue.Full:
                pass

    def _sacar(self, cola):
        while self.activo:
            try:
                return cola.get(timeout=0.2)
            except queue.Empty:
                pass
        return None

    def leer(self):
        # Siguiente frame para mostrar; None = fin del video
        return self._sacar(self.frames)

    def para_detectar(self):
        # (frame, segundo del video) para el detector; None = terminar
        return self._sacar(self.muestras)

    def detener(self):
        self.activo = False
        self.hilo.join(timeout=2)


class Detector:
    # Ejecuta el modelo en segundo plano, para que el video
    # no se congele mientras se detecta
    def __init__(self, lector, imgsz):
        self.lector   = lector
        self.imgsz    = imgsz
        self.duracion = 0   # segundos que tarda una detección (promedio)
        self.hechas   = 0
        self.activo   = True
        self.salida   = queue.Queue()
        self.hilo     = threading.Thread(target=self._detectar, daemon=True)
        self.hilo.start()

    def _detectar(self):
        global model
        try:
            model = tomar_modelo()
        except Exception as e:
            self.salida.put(e)
            return
        while self.activo:
            dato = self.lector.para_detectar()
            if dato is None:
                break
            frame, t = dato
            t0 = time.time()
            try:
                resultado = detectar(frame, self.imgsz)
            except Exception as e:
                self.salida.put(e)
                break
            # La primera detección incluye la carga del modelo: no se promedia
            d = time.time() - t0
            if self.hechas == 1:
                self.duracion = d
            elif self.hechas > 1:
                self.duracion = 0.7 * self.duracion + 0.3 * d
            self.hechas += 1
            self.salida.put((resultado, t))

    def recoger(self, esperar=False):
        # (resultado, hora de su imagen) de la detección más antigua sin recoger.
        # Si no hay ninguna lista devuelve (None, None), salvo que esperar=True
        while True:
            try:
                resultado = self.salida.get(timeout=0.2 if esperar else 0)
                break
            except queue.Empty:
                if not esperar or not self.hilo.is_alive():
                    return None, None
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    def detener(self):
        self.activo = False
        self.hilo.join(timeout=5)

# ============================================================
# FUNCIÓN: CERRAR RECURSOS
# ============================================================
def cerrar_recursos():
    global cap, archivo_csv, escritor, corriendo, lector, detector
    global model, last_results

    corriendo = False
    if led is not None:
        led.alertar(False)
    # Los hilos se detienen antes de soltar la cámara o el video
    if lector is not None:
        lector.detener()
        lector = None
    if detector is not None:
        detector.detener()
        detector = None
    if archivo_csv is not None:
        archivo_csv.close()
        archivo_csv = None
        escritor    = None
    if cap is not None:
        cap.release()
        cap = None
    cv2.destroyAllWindows()
    # Soltar el modelo de esta sesión: la próxima usa uno nuevo, y tener los
    # dos a la vez llenaba la memoria de la Raspberry (unos 150 MB de más)
    model = None
    last_results = None
    gc.collect()

# ============================================================
# BUCLE DE VIDEO
# ============================================================
def iniciar_video():
    global cap, model, entradas, salidas, frame_count, n_inferencias
    global last_results, inicio, zona_anterior, ultima_pos
    global archivo_csv, escritor, nombre_csv, pausado, corriendo
    global t_sesion
    global lector, detector

    preparar_led()

    # Abrir fuente
    cap = cv2.VideoCapture(FUENTE)
    if FUENTE == 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        cerrar_recursos()
        aviso("No se pudo abrir la fuente",
              "Revisa que la cámara esté conectada, o que la ruta del "
              "video sea correcta.", error=True)
        return

    # Ajustar líneas al tamaño del video
    global linea_verde, linea_roja
    ret, frame_init = cap.read()
    if not ret or frame_init is None:
        cerrar_recursos()
        aviso("La fuente no entrega imagen",
              "La cámara o el video abrieron, pero no entregaron ninguna "
              "imagen. Revisa la conexión de la cámara o prueba con otro "
              "video.", error=True)
        return
    es_camara = FUENTE == 0
    if not es_camara:
        frame_init = reducir(frame_init)
    H, W = frame_init.shape[:2]
    largo = W if ORIENTACION == "vertical" else H
    linea_verde = largo // 3
    linea_roja  = 2 * largo // 3
    # Si ya se acomodaron en una sesión anterior, quedan donde estaban
    clave_fuente = "camara" if es_camara else "video"
    recordadas   = lineas_recordadas(clave_fuente, largo)
    if recordadas is not None:
        linea_verde, linea_roja = recordadas
    if INVERTIDO:
        linea_verde, linea_roja = linea_roja, linea_verde
    reasig_dist = REASIG_DIST_PCT * H
    mov_min     = MOVIMIENTO_MIN if es_camara else 0

    # Inicializar variables
    entradas      = 0
    salidas       = 0
    frame_count   = 0
    n_inferencias = 0
    last_results  = None
    zona_anterior = {}
    ultima_pos    = {}
    pos_deteccion.clear()
    velocidad.clear()
    ancla.clear()
    confirmados.clear()
    t_deteccion   = 0
    inicio        = time.time()
    t_sesion      = 0.0
    historial.clear()
    pausado       = False
    corriendo     = True
    frame_base    = None
    m = s = 0

    # CSV: lleva el nombre del espacio; lo crea registrar_evento()
    espacio    = re.sub(r"[^\w-]+", "_", NOMBRE_ESPACIO).strip("_") or "espacio"
    nombre_csv = os.path.join(
        CARPETA_REGISTROS,
        f"motiva_{espacio}_{time.strftime('%Y%m%d_%H%M%S')}.csv")

    # Ventana video
    cv2.namedWindow("MOTIVA - Monitoreo", cv2.WINDOW_NORMAL)
    alto_total = ALTO_CABECERA + H + ALTO_PANEL
    escala     = min(960 / W, 760 / alto_total)
    if PANTALLA is not None:
        # Que quepa en la pantalla, con espacio para los bordes de la ventana
        escala = min(escala, (PANTALLA[0] - 40) / W,
                     (PANTALLA[1] - 160) / alto_total)
    ancho_v, alto_v = int(W * escala), int(alto_total * escala)
    cv2.resizeWindow("MOTIVA - Monitoreo", ancho_v, alto_v)
    if PANTALLA is not None:
        cv2.moveWindow("MOTIVA - Monitoreo",
                       max(0, (PANTALLA[0] - ancho_v) // 2),
                       max(0, (PANTALLA[1] - alto_v) // 2 - 50))
    cv2.setMouseCallback("MOTIVA - Monitoreo", mouse_callback)

    # La lectura y la detección corren en hilos aparte
    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
    if es_camara:
        lector   = LectorCamara(cap)
        detector = Detector(lector, IMGSZ or IMGSZ_CAMARA)
        visto    = 0
    else:
        lector   = LectorVideo(cap, fps_video)
        detector = Detector(lector, IMGSZ or IMGSZ_VIDEO)
    t_mostrar = time.time()

    # Bucle
    while corriendo:
        if pausado:
            # Redibujar para mostrar el indicador y poder mover las líneas
            if frame_base is not None:
                vista, _ = dibujar_ui(frame_base.copy(), entradas, salidas, m, s)
                cv2.imshow("MOTIVA - Monitoreo", vista)
            key = cv2.waitKey(100) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                pausado = False
                if es_camara:
                    # Las velocidades de antes de la pausa ya no sirven
                    velocidad.clear()
            continue

        if es_camara:
            visto, frame = lector.leer(visto)
            if frame is None:
                break
            frame = frame.copy()  # El original queda limpio para el detector
        else:
            frame = lector.leer()
            if frame is None:
                break

        frame_count += 1

        # Inferencia
        if es_camara:
            # En vivo: el detector trabaja sin parar sobre el frame más reciente
            nuevos, t_nuevos = detector.recoger()
            ahora = time.time()
            t_sesion = ahora - inicio
        else:
            # Video: 1 de cada INTERVAL frames se detectó por adelantado
            nuevos = None
            if frame_count % INTERVAL == 0:
                nuevos, t_nuevos = detector.recoger(esperar=True)
            ahora = frame_count / fps_video
            t_sesion = ahora

        if nuevos is not None:
            last_results  = nuevos
            t_deteccion   = t_nuevos
            n_inferencias += 1
            actualizar_velocidades(nuevos[0], t_deteccion)
            # Olvidar posiciones de IDs perdidos hace demasiado
            ultima_pos = {t: p for t, p in ultima_pos.items()
                          if n_inferencias - p[2] <= REASIG_INFERENCIAS}

        # Cuánto hay que adelantar las cajas: el tiempo que pasó desde
        # la imagen de la última detección
        adelanto = min(ahora - t_deteccion, ADELANTO_MAX)

        # Detectar cruces
        if last_results is not None and len(last_results) > 0:
            result = last_results[0]
            if result.boxes is not None and result.boxes.id is not None:
                boxes = result.boxes
                ids_actuales = {int(t) for t in boxes.id}
                for box, track_id in zip(boxes.xyxy, boxes.id):
                    x1, y1, x2, y2 = map(int, box.tolist())
                    tid = int(track_id)
                    cx  = (x1 + x2) // 2
                    cy  = (y1 + y2) // 2

                    # ID nuevo: heredar la zona del ID perdido más cercano
                    if tid not in zona_anterior:
                        mejor, mejor_d = None, reasig_dist
                        for otro, (ox, oy, _) in ultima_pos.items():
                            if otro in ids_actuales:
                                continue
                            d = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
                            if d <= mejor_d:
                                mejor, mejor_d = otro, d
                        if mejor is not None:
                            zona_anterior[tid] = zona_anterior.pop(mejor)
                            del ultima_pos[mejor]
                            confirmados.add(tid)

                    # Solo vale como persona si se movió desde su ancla, o si
                    # cambió de tamaño: quien camina de frente a la cámara
                    # casi no se desplaza, pero se agranda o se achica
                    lado = max(x2 - x1, y2 - y1)
                    ax, ay, ta, lado_a = ancla.setdefault(
                        tid, (cx, cy, t_deteccion, lado))
                    d = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
                    cambio = abs(lado - lado_a) / max(lado_a, 1)
                    if d >= mov_min * lado or cambio >= TAMANO_MIN:
                        ancla[tid] = (cx, cy, t_deteccion, lado)
                        confirmados.add(tid)
                    elif t_deteccion - ta > QUIETO_MAX:
                        confirmados.discard(tid)

                    zona_actual = get_zona(cx, cy)
                    if tid not in confirmados:
                        # Se guarda la última zona válida, para contar su
                        # cruce cuando se confirme que es una persona
                        zona_anterior.setdefault(tid, zona_actual)
                        continue
                    zona_prev   = zona_anterior.get(tid, zona_actual)

                    if zona_prev == "arriba" and zona_actual in ("medio", "abajo"):
                        entradas += 1
                        registrar_evento()

                    elif zona_prev in ("medio", "abajo") and zona_actual == "arriba":
                        salidas += 1
                        registrar_evento()

                    zona_anterior[tid] = zona_actual
                    ultima_pos[tid]    = (cx, cy, n_inferencias)

                    # El conteo usa la posición detectada; solo el dibujo se adelanta
                    vx, vy = velocidad.get(tid, (0, 0))
                    dx = int(vx * adelanto)
                    dy = int(vy * adelanto)
                    cv2.rectangle(frame, (x1 + dx, y1 + dy), (x2 + dx, y2 + dy),
                                  V_VERDE, 2)
                    poner_chapa(frame, f"PERSON ID {tid}",
                                x1 + dx - 1, y1 + dy - 18, V_VERDE, tam=10)

        # Tiempo
        st = int(time.time() - inicio)
        m  = st // 60
        s  = st % 60

        frame_base = frame.copy()  # Sin UI, para redibujar en pausa
        frame, ocupacion = dibujar_ui(frame, entradas, salidas, m, s)
        if led is not None:
            led.alertar(ocupacion > AFORO_MAX)
        cv2.imshow("MOTIVA - Monitoreo", frame)

        # Video: repartir los frames de forma pareja, al ritmo que aguanta
        # la detección y sin pasar de la velocidad real del video
        espera = 1
        if not es_camara:
            paso      = max(1 / fps_video, detector.duracion / INTERVAL)
            t_mostrar = max(t_mostrar + paso, time.time())
            espera    = max(1, int((t_mostrar - time.time()) * 1000))

        key = cv2.waitKey(espera) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            pausado = not pausado

    # Cierre
    recordar_lineas(clave_fuente, largo)
    registro = nombre_csv if archivo_csv is not None else "ninguno (no hubo conteos)"
    cerrar_recursos()

    st = int(time.time() - inicio)
    m  = st // 60
    s  = st % 60

    print("\n========================================")
    print("     RESUMEN FINAL - MOTIVA")
    print("========================================")
    print(f"  Espacio:         {NOMBRE_ESPACIO}")
    print(f"  Duracion:        {m:02d}:{s:02d}")
    print(f"  Entradas:        {entradas}")
    print(f"  Salidas:         {salidas}")
    print(f"  Ocupacion final: {max(0, entradas - salidas)}")
    print(f"  CSV guardado:    {registro}")
    print("========================================\n")

    # Con conteos se muestra el informe con la gráfica; se guarda junto al CSV
    if historial:
        try:
            ruta_informe = os.path.splitext(nombre_csv)[0] + ".png"
            cv2.imwrite(ruta_informe, dibujar_informe(
                historial, t_sesion,
                "Cámara web" if es_camara else os.path.basename(FUENTE),
                time.strftime("%d/%m/%Y %H:%M", time.localtime(inicio))))
            if mostrar_informe(ruta_informe):
                return
        except Exception as e:
            print(f"No se pudo generar el informe: {e}")

    aviso("Sesión finalizada",
          f"{NOMBRE_ESPACIO} · duración {hora_corta(st)}\n\n"
          f"No hubo entradas ni salidas en esta sesión, así que no se "
          f"guardó registro ni informe.")

# ============================================================
# INTERFAZ: PIEZAS COMUNES (CustomTkinter)
# ============================================================
def letra(tam, negrita=False):
    return ctk.CTkFont(family=LETRA, size=tam,
                       weight="bold" if negrita else "normal")

def icono_play(lado=14, color="#111111"):
    # Triángulo de "iniciar" dibujado, para el botón principal
    img = Image.new("RGBA", (lado * 4, lado * 4), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon(
        [(lado * 0.6, lado * 0.4), (lado * 3.5, lado * 2), (lado * 0.6, lado * 3.6)],
        fill=color)
    img = img.resize((lado, lado), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(lado, lado))

class Selector(ctk.CTkSegmentedButton):
    # Botones pegados de los que queda marcado uno solo. Muestra textos pero
    # guarda en `variable` el valor de cada opción ("camara", 320, True...)
    def __init__(self, master, variable, opciones, **kw):
        self.opciones = list(opciones)
        self.variable_real = variable
        super().__init__(master, values=[t for t, _ in self.opciones],
                         command=self._elegido,
                         font=letra(13), height=34, corner_radius=8,
                         border_width=2, fg_color=C_BORDE,
                         selected_color=C_ACENTO,
                         selected_hover_color=C_ACENTO2,
                         unselected_color=C_CAMPO,
                         unselected_hover_color=C_BORDE,
                         text_color=C_TEXTO,
                         text_color_disabled=C_APAGADO,
                         dynamic_resizing=True, **kw)
        variable.trace_add("write", lambda *_: self._mostrar())
        self._mostrar()

    def _elegido(self, texto):
        for t, v in self.opciones:
            if t == texto:
                self.variable_real.set(v)

    def _mostrar(self):
        for t, v in self.opciones:
            if v == self.variable_real.get():
                self.set(t)

    def renombrar(self, textos):
        # Cambia los nombres visibles sin cambiar los valores
        self.opciones = [(t, v) for t, (_, v) in zip(textos, self.opciones)]
        self.configure(values=textos)
        self._mostrar()

    # Texto oscuro sobre el amarillo de la opción elegida, claro en las demás
    def _select_button_by_value(self, value):
        super()._select_button_by_value(value)
        self._buttons_dict[value].configure(text_color="#111111")

    def _unselect_button_by_value(self, value):
        super()._unselect_button_by_value(value)
        if value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=C_TEXTO)

def centrar(ventana, subir=0):
    ventana.update_idletasks()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    x = max(0, (ventana.winfo_screenwidth() - ancho) // 2)
    y = max(0, (ventana.winfo_screenheight() - alto) // 2 - subir)
    ventana.geometry(f"+{x}+{y}")

def esperar_modelo(ventana):
    # Si el modelo aún se está preparando, lo dice con una barra de progreso
    # y espera aquí, con el menú quieto: esperar con la ventana de video ya
    # abierta lo demoraba varias veces más. Devuelve False si no se pudo cargar
    precargar_modelo()
    if hilo_modelo.is_alive():
        v = ctk.CTkToplevel(fg_color=C_FONDO)
        v.title("MOTIVA - Preparando")
        v.resizable(False, False)
        v.protocol("WM_DELETE_WINDOW", lambda: None)   # no se cierra a medias
        cuerpo = ctk.CTkFrame(v, fg_color="transparent")
        cuerpo.pack(padx=30, pady=24)
        ctk.CTkLabel(cuerpo, text="Preparando el detector", font=letra(17, True),
                     text_color=C_TEXTO).pack(anchor="w")
        ctk.CTkLabel(cuerpo, text="La primera vez después de abrir MOTIVA "
                     "tarda unos segundos.", font=letra(13),
                     text_color=C_SUAVE).pack(anchor="w", pady=(4, 14))
        barra = ctk.CTkProgressBar(cuerpo, width=360, height=8,
                                   mode="indeterminate", fg_color=C_CAMPO,
                                   progress_color=C_ACENTO)
        barra.pack(fill="x")
        barra.start()
        centrar(v, 40)
        v.update()
        try:
            v.grab_set()   # que no se pueda pulsar INICIAR otra vez mientras tanto
        except tk.TclError:
            pass
        while hilo_modelo.is_alive():
            ventana.update()
            time.sleep(0.05)
        barra.stop()
        v.destroy()
        ventana.update()
    return modelo_previo is not None

def aviso(titulo, mensaje, error=False):
    # Cuadro de mensaje con el aspecto de la app; espera a que lo cierren.
    # Sin ventana principal (pruebas sin pantalla) solo lo escribe en la terminal
    print(f"{titulo}: {mensaje}")
    if tk._default_root is None:
        return
    v = ctk.CTkToplevel(fg_color=C_FONDO)
    v.title(f"MOTIVA - {titulo}")
    v.resizable(False, False)
    cuerpo = ctk.CTkFrame(v, fg_color="transparent")
    cuerpo.pack(padx=28, pady=(24, 20))
    fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
    fila.pack(anchor="w")
    ctk.CTkFrame(fila, width=10, height=10, corner_radius=5,
                 fg_color=C_ROJO if error else C_ACENTO).pack(
                 side="left", padx=(0, 10))
    ctk.CTkLabel(fila, text=titulo, font=letra(17, True),
                 text_color=C_TEXTO).pack(side="left")
    ctk.CTkLabel(cuerpo, text=mensaje, font=letra(14),
                 text_color=C_TEXTO, justify="left", anchor="w",
                 wraplength=420).pack(anchor="w", pady=(10, 18))
    boton = ctk.CTkButton(cuerpo, text="Entendido", font=letra(14, True),
                          width=130, height=38, corner_radius=8,
                          fg_color=C_ACENTO, hover_color=C_ACENTO2,
                          text_color="#111111", command=v.destroy)
    boton.pack(anchor="e")
    v.bind("<Return>", lambda e: v.destroy())
    v.bind("<Escape>", lambda e: v.destroy())
    centrar(v, 40)
    v.after(50, lambda: (v.lift(), v.focus_force(), v.grab_set()))
    v.wait_window()

# ============================================================
# INTERFAZ: MENÚ
# ============================================================
def iniciar_app():
    global AFORO_MAX, NOMBRE_ESPACIO, FUENTE, INTERVAL

    cargar_config()
    iniciar_pagina_web()

    def recordado(clave, defecto, validos=None):
        # Lo guardado en la última sesión, o el de fábrica si no sirve
        valor = CONFIG.get(clave, defecto)
        if type(valor) is not type(defecto):
            return defecto
        if validos is not None and valor not in validos:
            return defecto
        return valor

    ctk.set_appearance_mode("dark")
    ventana = ctk.CTk(fg_color=C_FONDO)
    ventana.title("MOTIVA - Sistema de Monitoreo")
    ventana.resizable(False, False)
    try:
        ventana.iconphoto(True, tk.PhotoImage(file=ICONO))
    except tk.TclError:
        pass  # sin el archivo del ícono el menú funciona igual

    # ---- Piezas con las que se arma el menú ----
    def tarjeta(columna, titulo):
        # Bloque con título que agrupa opciones; devuelve el marco donde van
        ctk.CTkLabel(columna, text=titulo, font=letra(15, True),
                     text_color=C_TEXTO, height=20).pack(
                     anchor="w", padx=4, pady=(14, 6))
        marco = ctk.CTkFrame(columna, fg_color=C_TARJETA, corner_radius=12,
                             border_width=1, border_color=C_BORDE)
        marco.pack(fill="x")
        dentro = ctk.CTkFrame(marco, fg_color="transparent")
        dentro.pack(fill="x", padx=16, pady=10)
        return dentro

    def etiqueta(marco, fila, texto):
        lbl = ctk.CTkLabel(marco, text=texto, font=letra(14), width=118,
                           anchor="w", text_color=C_TEXTO)
        lbl.grid(row=fila, column=0, sticky="w", pady=5)
        return lbl

    def campo(marco, ancho):
        e = ctk.CTkEntry(marco, width=ancho, height=34, corner_radius=8,
                         font=letra(14), fg_color=C_CAMPO,
                         border_width=1, border_color=C_BORDE,
                         text_color=C_TEXTO)
        # El borde se pinta de amarillo en el campo que está en uso
        e.bind("<FocusIn>", lambda _: e.configure(border_color=C_ACENTO))
        e.bind("<FocusOut>", lambda _: e.configure(border_color=C_BORDE))
        return e

    def poner_texto_campo(e, texto):
        e.delete(0, "end")
        e.insert(0, texto)

    def nota(marco, texto):
        return ctk.CTkLabel(marco, text=texto, font=letra(12),
                            text_color=C_SUAVE, height=18, anchor="w")

    # ---- Encabezado: la red, el logo y los títulos (se dibuja al final,
    # cuando ya se sabe el ancho de la ventana) ----
    cabecera = ctk.CTkLabel(ventana, text="", height=112)
    cabecera.pack(fill="x")

    # ---- Dos columnas, para que quepa en pantallas de 768 px de alto ----
    cuerpo = ctk.CTkFrame(ventana, fg_color="transparent")
    cuerpo.pack(fill="x", padx=26)
    cuerpo.grid_columnconfigure((0, 1), weight=1, uniform="columna")
    col_izq = ctk.CTkFrame(cuerpo, fg_color="transparent")
    col_izq.grid(row=0, column=0, sticky="new", padx=(0, 10))
    col_der = ctk.CTkFrame(cuerpo, fg_color="transparent")
    col_der.grid(row=0, column=1, sticky="new", padx=(10, 0))

    # ---- Espacio ----
    t_espacio = tarjeta(col_izq, "Espacio")

    etiqueta(t_espacio, 0, "Nombre")
    entry_nombre = campo(t_espacio, 292)
    poner_texto_campo(entry_nombre, recordado("nombre", "Salon E3T"))
    entry_nombre.grid(row=0, column=1, sticky="w")

    etiqueta(t_espacio, 1, "Aforo máximo")
    frame_aforo = ctk.CTkFrame(t_espacio, fg_color="transparent")
    frame_aforo.grid(row=1, column=1, sticky="w")
    entry_aforo = campo(frame_aforo, 80)
    poner_texto_campo(entry_aforo, str(recordado("aforo", 20)))
    entry_aforo.pack(side="left")
    nota(frame_aforo, "personas").pack(side="left", padx=10)

    # ---- Fuente de video ----
    t_fuente = tarjeta(col_izq, "Fuente de video")

    fuente_var = tk.StringVar(
        value=recordado("fuente", "camara", ("camara", "video")))

    etiqueta(t_fuente, 0, "Fuente")
    Selector(t_fuente, fuente_var,
             [("Cámara web", "camara"), ("Video", "video")]).grid(
             row=0, column=1, sticky="w")

    # Ruta del video
    lbl_ruta = etiqueta(t_fuente, 1, "Archivo")
    frame_ruta = ctk.CTkFrame(t_fuente, fg_color="transparent")
    frame_ruta.grid(row=1, column=1, sticky="w")

    entry_ruta = campo(frame_ruta, 204)
    poner_texto_campo(entry_ruta,
                      recordado("ruta", os.path.join(CARPETA, "video3.mp4")))
    entry_ruta.pack(side="left")

    def buscar_video():
        ruta = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Videos", "*.mp4 *.avi *.mov *.mkv")]
        )
        if ruta:
            poner_texto_campo(entry_ruta, ruta)

    btn_buscar = ctk.CTkButton(frame_ruta, text="Buscar", font=letra(13),
                               width=80, height=34, corner_radius=8,
                               fg_color=C_CAMPO, hover_color=C_BORDE,
                               border_width=1, border_color=C_BORDE,
                               text_color=C_TEXTO,
                               text_color_disabled=C_APAGADO,
                               command=buscar_video)
    btn_buscar.pack(side="left", padx=(8, 0))

    # Intervalo de inferencia
    lbl_intervalo = etiqueta(t_fuente, 2, "Intervalo")
    frame_interval = ctk.CTkFrame(t_fuente, fg_color="transparent")
    frame_interval.grid(row=2, column=1, sticky="w")

    lbl_valor = ctk.CTkLabel(frame_interval, font=letra(13), width=150,
                             anchor="w", text_color=C_TEXTO)

    def mostrar_intervalo(valor):
        n = int(round(float(valor)))
        lbl_valor.configure(text="analiza todas las imágenes" if n == 1
                            else f"analiza 1 de cada {n} imágenes")

    scale_interval = ctk.CTkSlider(frame_interval, from_=1, to=10,
                                   number_of_steps=9, width=136, height=18,
                                   fg_color=C_CAMPO, progress_color=C_ACENTO,
                                   button_color=C_ACENTO,
                                   button_hover_color=C_ACENTO2,
                                   command=mostrar_intervalo)
    scale_interval.set(recordado("intervalo", 5, range(1, 11)))
    scale_interval.pack(side="left")
    lbl_valor.pack(side="left", padx=(12, 0))
    mostrar_intervalo(scale_interval.get())

    nota_intervalo = nota(t_fuente, "Solo para video. Mayor = más rápido")
    nota_intervalo.grid(row=3, column=1, sticky="w", pady=(0, 2))

    # ---- Conteo ----
    t_conteo = tarjeta(col_der, "Conteo")

    # Orientación de las líneas
    orientacion_var = tk.StringVar(
        value=recordado("orientacion", "horizontal",
                        ("horizontal", "vertical")))

    etiqueta(t_conteo, 0, "Líneas")
    Selector(t_conteo, orientacion_var,
             [("Horizontales", "horizontal"), ("Verticales", "vertical")]
             ).grid(row=0, column=1, sticky="w")

    # Sentido de entrada
    invertido_var = tk.BooleanVar(value=recordado("invertido", False))

    etiqueta(t_conteo, 1, "Se entra")
    selector_sentido = Selector(t_conteo, invertido_var,
                                [("Hacia abajo", False),
                                 ("Hacia arriba", True)])
    selector_sentido.grid(row=1, column=1, sticky="w")

    def nombrar_sentidos(*_):
        # Los nombres dependen de cómo estén puestas las líneas
        if orientacion_var.get() == "vertical":
            selector_sentido.renombrar(["Hacia la derecha",
                                        "Hacia la izquierda"])
        else:
            selector_sentido.renombrar(["Hacia abajo", "Hacia arriba"])

    orientacion_var.trace_add("write", nombrar_sentidos)
    nombrar_sentidos()

    # ---- Calidad de detección (va con la fuente: cada una recuerda la suya) ----
    calidades = {"camara": IMGSZ_CAMARA, "video": IMGSZ_VIDEO}
    for clave, tam in recordado("calidad", {}).items():
        if clave in calidades and tam in (320, 480, 640):
            calidades[clave] = tam

    imgsz_var = tk.IntVar(value=calidades[fuente_var.get()])

    etiqueta(t_fuente, 4, "Calidad").grid(pady=(10, 5))
    Selector(t_fuente, imgsz_var,
             [("Rápida", 320), ("Media", 480), ("Precisa", 640)]).grid(
             row=4, column=1, sticky="w", pady=(10, 5))

    nota(t_fuente,
         "Rápida = más fluido. Precisa = ve mejor de lejos").grid(
         row=5, column=1, sticky="w", pady=(0, 2))

    # ---- Ayuda para el monitoreo ----
    t_ayuda = tarjeta(col_der, "Durante el monitoreo")
    ayudas = [("Mouse", "arrastra las líneas para ubicarlas"),
              ("Espacio", "pausa o reanuda"),
              ("Q", "termina la sesión y muestra el informe")]
    if URL_WEB is not None:
        ayudas.append(("Celular", URL_WEB))
    for fila, (tecla, texto) in enumerate(ayudas):
        etiqueta(t_ayuda, fila, tecla).configure(height=24)
        ctk.CTkLabel(t_ayuda, text=texto, font=letra(13), height=24,
                     text_color=C_SUAVE, anchor="w").grid(
                     row=fila, column=1, sticky="w")

    def segun_fuente(*_):
        # La ruta y el intervalo solo sirven con video, y al cambiar de
        # fuente se vuelve a la calidad que se usó con esa fuente
        es_video = fuente_var.get() == "video"
        estado   = "normal" if es_video else "disabled"
        color    = C_TEXTO if es_video else C_APAGADO
        entry_ruta.configure(state=estado,
                             text_color=C_TEXTO if es_video else C_APAGADO,
                             fg_color=C_CAMPO if es_video else C_TARJETA)
        btn_buscar.configure(state=estado,
                             fg_color=C_CAMPO if es_video else C_TARJETA)
        scale_interval.configure(
            state=estado,
            button_color=C_ACENTO if es_video else C_APAGADO,
            progress_color=C_ACENTO if es_video else C_APAGADO)
        for lbl in (lbl_ruta, lbl_intervalo, lbl_valor):
            lbl.configure(text_color=color)
        nota_intervalo.configure(text_color=C_SUAVE if es_video else C_APAGADO)
        imgsz_var.set(calidades[fuente_var.get()])

    def anotar_calidad(*_):
        calidades[fuente_var.get()] = imgsz_var.get()

    fuente_var.trace_add("write", segun_fuente)
    segun_fuente()
    imgsz_var.trace_add("write", anotar_calidad)

    # ---- Botón Iniciar ----
    def on_iniciar():
        global AFORO_MAX, NOMBRE_ESPACIO, FUENTE, INTERVAL, ORIENTACION
        global INVERTIDO, IMGSZ, PANTALLA

        # Validar aforo
        try:
            AFORO_MAX = int(entry_aforo.get())
        except ValueError:
            AFORO_MAX = 0
        if AFORO_MAX < 1:
            aviso("Revisa el aforo",
                  "El aforo máximo debe ser un número entero de 1 en "
                  "adelante, por ejemplo 20.", error=True)
            entry_aforo.focus_set()
            return

        NOMBRE_ESPACIO = entry_nombre.get().strip()
        if not NOMBRE_ESPACIO:
            aviso("Falta el nombre",
                  "Escribe el nombre del espacio que se va a monitorear.",
                  error=True)
            entry_nombre.focus_set()
            return

        INTERVAL    = int(round(scale_interval.get()))
        ORIENTACION = orientacion_var.get()
        INVERTIDO   = invertido_var.get()
        IMGSZ       = imgsz_var.get()
        PANTALLA    = (ventana.winfo_screenwidth(),
                       ventana.winfo_screenheight())

        if fuente_var.get() == "camara":
            FUENTE = 0
        else:
            FUENTE = entry_ruta.get().strip()
            if not FUENTE:
                aviso("Falta el video",
                      "Escribe la ruta del video o búscalo con el botón "
                      "Buscar.", error=True)
                return

        if not esperar_modelo(ventana):
            aviso("No se pudo cargar el detector",
                  f"El modelo de detección no se pudo abrir:\n{error_modelo}",
                  error=True)
            precargar_modelo()   # se reintenta para la próxima vez
            return

        # Recordar estas opciones para la próxima vez
        CONFIG.update(nombre=NOMBRE_ESPACIO, aforo=AFORO_MAX,
                      fuente=fuente_var.get(),
                      ruta=entry_ruta.get().strip(),
                      intervalo=INTERVAL, orientacion=ORIENTACION,
                      invertido=INVERTIDO, calidad=dict(calidades))
        guardar_config()

        ventana.withdraw()  # Ocultar ventana config
        ventana.update()

        # El video corre en el hilo principal: OpenCV y los cuadros de
        # mensaje no son seguros desde un hilo secundario
        try:
            iniciar_video()
        except Exception as e:
            aviso("El sistema se detuvo",
                  f"Ocurrió un error durante el monitoreo:\n{e}", error=True)
            raise
        finally:
            cerrar_recursos()   # Libera camara y CSV aunque haya fallado
            ventana.deiconify()  # Mostrar ventana config de nuevo
            precargar_modelo()   # el de la próxima sesión

    btn_iniciar = ctk.CTkButton(ventana, text="INICIAR SISTEMA",
                                image=icono_play(), compound="left",
                                font=letra(16, True), height=50,
                                corner_radius=10, fg_color=C_ACENTO,
                                hover_color=C_ACENTO2, text_color="#111111",
                                command=on_iniciar)
    btn_iniciar.pack(fill="x", padx=26, pady=(24, 10))
    ventana.bind("<Return>", lambda e: on_iniciar())

    # ---- Versión ----
    nota(ventana, "MOTIVA v2.0 · 2026").pack(pady=(2, 16))

    ventana.update_idletasks()
    ancho = ventana.winfo_reqwidth()
    cabecera.configure(image=ctk.CTkImage(light_image=banner_menu(ancho),
                                          dark_image=banner_menu(ancho),
                                          size=(ancho, 112)))
    centrar(ventana)
    # El modelo se prepara mientras se llena el menú. Se arranca después de
    # mostrarlo: cargar la librería a la vez demoraba el menú unos 3 s
    ventana.after(400, precargar_modelo)
    ventana.mainloop()

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    iniciar_app()
    # Al cerrar el menú puede quedar un modelo preparándose en segundo plano.
    # Se termina sin esperarlo: la librería del modelo aborta si el programa
    # se cierra normalmente con ella trabajando
    if led is not None:
        led.cerrar()
    sys.stdout.flush()
    os._exit(0)
