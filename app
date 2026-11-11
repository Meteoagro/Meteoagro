"""
MeteoAgro (beta) - App en Streamlit.

Cómo correrla (PowerShell, dentro de esta carpeta):
    python -m streamlit run app.py
"""
from __future__ import annotations

import html
import os

import streamlit as st

import pandas as pd

from dmc import (ErrorDMC, cargar_guardados, descargar_recientes, descargar_resumen,
                 hora_chile, leer_estaciones, leer_recientes, mas_cercana, numero_chileno)
from reglas import FICHAS, ORDEN_NIVEL, evaluar

st.set_page_config(page_title="MeteoAgro", page_icon="🌱", layout="centered")

# Lugares de ejemplo: coordenadas aproximadas del centro de cada ciudad.
LUGARES = {
    "Curicó": (-34.985, -71.239),
    "Molina": (-35.114, -71.283),
    "Talca": (-35.426, -71.655),
    "Linares": (-35.846, -71.598),
    "San Fernando": (-34.586, -70.988),
    "Rancagua": (-34.170, -70.744),
    "Santiago": (-33.449, -70.669),
    "Chillán": (-36.607, -72.103),
}
OTRA = "Otra ubicación (coordenadas)"
NIVEL_TEXTO = {"critico": "Crítico", "atencion": "Atención", "ok": "Sin alertas"}

ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
html, body, .stApp, .stMarkdown, button, input, textarea, select, label {
  font-family: 'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif;
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 560px; padding-top: 3.5rem; padding-bottom: 3rem; }
.ma-logo { font-size: 2.2rem; font-weight: 800; color: #2F6B3C; letter-spacing: -0.5px; line-height: 1.1; }
.ma-lema { color: #4A554C; font-size: 1rem; margin-bottom: 0.3rem; }
.ma-fuente { display: inline-block; font-size: 0.85rem; font-weight: 700; padding: 0.25rem 0.75rem;
  border-radius: 999px; margin: 0.2rem 0 0.8rem; }
.ma-fuente.vivo { background: #DCEAD1; color: #234F2C; }
.ma-fuente.guardado { background: #F3D9C6; color: #7A3A12; }
.ma-fuente.simulacion { background: #C98A1F; color: #1F2A21; }
.ma-card { background: #FFFDF8; border: 2px solid #E4DCCB; border-radius: 18px;
  padding: 1rem 1.1rem; margin-bottom: 0.8rem; }
.ma-card h4 { margin: 0 0 0.2rem; padding: 0; font-size: 1.2rem; font-weight: 800; color: #1F2A21; }
.ma-sub { color: #4A554C; font-size: 0.92rem; margin: 0 0 0.7rem; }
.ma-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem 1rem; }
.ma-dato { font-size: 0.85rem; color: #4A554C; }
.ma-valor { font-size: 1.35rem; font-weight: 800; color: #1F2A21; line-height: 1.2; }
.ma-alerta { border-radius: 18px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem; }
.ma-alerta .ma-nivel { text-transform: uppercase; letter-spacing: 1px; font-size: 0.75rem; font-weight: 800; }
.ma-alerta .t { font-weight: 800; font-size: 1.1rem; margin: 0.1rem 0 0.2rem; }
.ma-alerta .d { font-size: 0.95rem; margin-bottom: 0.35rem; }
.ma-alerta .a { font-size: 0.95rem; font-weight: 700; }
.ma-alerta.critico { background: #B23B2E; color: #F7F3EA; }
.ma-alerta.atencion { background: #C98A1F; color: #1F2A21; }
.ma-alerta.ok { background: #2F6B3C; color: #F7F3EA; }
.ma-auspicio { border: 2px dashed #B9AE96; border-radius: 14px; padding: 0.8rem; text-align: center;
  color: #4A554C; font-size: 0.9rem; margin: 0.9rem 0; }
.ma-lista { margin: 0.3rem 0 0.6rem 1.1rem; padding: 0; color: #1F2A21; }
.ma-lista li { margin-bottom: 0.3rem; }
.ma-pie { color: #4A554C; font-size: 0.8rem; margin-top: 1.5rem; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


def esc(texto) -> str:
    return html.escape(str(texto))


def con_unidad(valor, unidad: str, decimales: int = 1) -> str:
    if valor is None:
        return "sin dato"
    return f"{numero_chileno(valor, decimales)} {unidad}"


def dato(etiqueta: str, valor: str) -> str:
    return f'<div><div class="ma-dato">{esc(etiqueta)}</div><div class="ma-valor">{esc(valor)}</div></div>'


def tarjeta_alerta(a) -> str:
    return (f'<div class="ma-alerta {a.nivel}"><div class="ma-nivel">{NIVEL_TEXTO[a.nivel]}</div>'
            f'<div class="t">{esc(a.titulo)}</div><div class="d">{esc(a.detalle)}</div>'
            f'<div class="a">{esc(a.accion)}</div></div>')


@st.cache_data(ttl=600, show_spinner=False)
def datos_en_vivo(usuario: str, token: str) -> dict:
    return descargar_resumen(usuario, token)


@st.cache_data(show_spinner=False)
def datos_guardados() -> dict:
    return cargar_guardados()


@st.cache_data(ttl=600, show_spinner=False)
def recientes_en_vivo(usuario: str, token: str, codigo: str) -> list:
    return leer_recientes(descargar_recientes(usuario, token, codigo))


# --------------------------------------------------------------------------
# Ajustes (barra lateral): de dónde salen los datos
# --------------------------------------------------------------------------
def secreto(nombre: str) -> str:
    """Lee un secreto de Streamlit Cloud o, si no hay, una variable de entorno."""
    try:
        valor = st.secrets.get(nombre, "")
    except Exception:  # en el computador normalmente no hay archivo de secretos
        valor = ""
    return str(valor or os.environ.get(nombre, "")).strip()


USUARIO_PROYECTO = secreto("DMC_USUARIO")
TOKEN_PROYECTO = secreto("DMC_TOKEN")
CUENTA_PROYECTO = bool(USUARIO_PROYECTO and TOKEN_PROYECTO)

with st.sidebar:
    st.markdown("### Ajustes de datos")
    usar_vivo = st.toggle("Usar datos en vivo de la DMC", value=CUENTA_PROYECTO)
    if CUENTA_PROYECTO:
        usuario, token = USUARIO_PROYECTO, TOKEN_PROYECTO
        st.caption("Conectada con la cuenta DMC del proyecto.")
    else:
        usuario = st.text_input("Correo registrado en la DMC", value="", disabled=not usar_vivo)
        token = st.text_input("API key de la DMC", value="", type="password",
                              disabled=not usar_vivo)
    st.caption("Si la DMC no responde, la app muestra la consulta real "
               "guardada el 10-11-2026.")

fuente = "guardado"
aviso = None
geojson = None
if usar_vivo and usuario.strip() and token.strip():
    try:
        with st.spinner("Consultando la DMC..."):
            geojson = datos_en_vivo(usuario.strip(), token.strip())
        fuente = "vivo"
    except ErrorDMC as error:
        aviso = (f"No se pudo usar la DMC en vivo: {error} "
                 "Te muestro los datos guardados del 10-11-2026.")
elif usar_vivo:
    aviso = "Para usar datos en vivo, escribe tu correo y tu API key en Ajustes."

if geojson is None:
    geojson = datos_guardados()
estaciones = leer_estaciones(geojson)

# --------------------------------------------------------------------------
# Encabezado
# --------------------------------------------------------------------------
st.markdown('<div class="ma-logo">MeteoAgro</div>'
            '<div class="ma-lema">El clima de tu campo, directo y simple.</div>',
            unsafe_allow_html=True)
if aviso:
    st.warning(aviso)

tab_inicio, tab_alertas, tab_cultivos, tab_pregunta, tab_perfil = st.tabs(
    ["Inicio", "Alertas", "Mis cultivos", "Pregúntale", "Perfil"])

# --------------------------------------------------------------------------
# Inicio
# --------------------------------------------------------------------------
with tab_inicio:
    lugar = st.selectbox("¿Dónde está tu campo?", list(LUGARES) + [OTRA])
    if lugar == OTRA:
        col1, col2 = st.columns(2)
        lat = col1.number_input("Latitud", value=-34.985, min_value=-56.0,
                                max_value=-17.0, format="%.4f")
        lon = col2.number_input("Longitud", value=-71.239, min_value=-76.0,
                                max_value=-66.0, format="%.4f")
    else:
        lat, lon = LUGARES[lugar]

    cultivos = st.multiselect("¿Qué cultivas?", list(FICHAS), default=["palto"],
                              format_func=lambda k: FICHAS[k].nombre)

    estacion, km = mas_cercana(estaciones, lat, lon)
    actualizado = hora_chile(estacion.actualizado_utc)
    if fuente == "vivo":
        st.markdown(f'<span class="ma-fuente vivo">Datos en vivo de la DMC · '
                    f'{esc(actualizado)}</span>', unsafe_allow_html=True)
        if st.button("Actualizar datos ahora"):
            datos_en_vivo.clear()
            recientes_en_vivo.clear()
            st.rerun()
    else:
        st.markdown(f'<span class="ma-fuente guardado">Datos guardados de la DMC · '
                    f'{esc(actualizado)}</span>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="ma-card"><h4>{esc(estacion.nombre)}</h4>'
        f'<p class="ma-sub">Estación DMC más cercana · a {numero_chileno(km)} km · '
        f'{esc(estacion.comuna)}</p><div class="ma-grid">'
        + dato("Temperatura", con_unidad(estacion.temperatura, "°C"))
        + dato("Humedad", con_unidad(estacion.humedad, "%", 0))
        + dato("Mínima reciente", con_unidad(estacion.tmin_reciente, "°C"))
        + dato("Máxima reciente", con_unidad(estacion.tmax_reciente, "°C"))
        + dato("Lluvia reciente", con_unidad(estacion.lluvia_reciente, "mm"))
        + dato("Actualizado", actualizado)
        + '</div></div>',
        unsafe_allow_html=True)
    st.caption("“Reciente” = lo más extremo entre hoy y ayer en la estación.")

    # Gráfico de las últimas 12 horas (solo con datos en vivo)
    if fuente == "vivo":
        try:
            serie = recientes_en_vivo(usuario.strip(), token.strip(), estacion.codigo)
        except ErrorDMC:
            serie = []
        serie = [f for f in serie if f["temperatura"] is not None]
        if serie:
            st.markdown("#### Últimas 12 horas en la estación")
            tabla = pd.DataFrame(serie).set_index("hora")
            tabla = tabla[["temperatura", "rocio"]].resample("10min").mean().dropna(how="all")
            tabla = tabla.rename(columns={"temperatura": "Temperatura (°C)",
                                          "rocio": "Punto de rocío (°C)"})
            st.line_chart(tabla[["Temperatura (°C)", "Punto de rocío (°C)"]],
                          color=["#B23B2E", "#2F6B3C"], x_label="Hora de Chile",
                          y_label="°C", height=260)
            ultima = serie[-1]
            st.caption(
                f"Mínima de las últimas 12 horas: "
                f"{numero_chileno(min(f['temperatura'] for f in serie))} °C · "
                f"viento ahora: {numero_chileno(ultima['viento_kmh'])} km/h. "
                "El punto de rocío muestra cuánta humedad tiene el aire: si está muy bajo, "
                "la noche se enfría más rápido.")

    zona_alertas = st.container()

    with st.expander("Probar con otro clima (simulación)"):
        simular = st.toggle("Activar simulación", value=False)
        s_tmin = st.slider("Temperatura mínima (°C)", -6.0, 20.0, -1.0, 0.5, disabled=not simular)
        s_tmax = st.slider("Temperatura máxima (°C)", 10.0, 42.0, 28.0, 0.5, disabled=not simular)
        s_lluvia = st.slider("Lluvia en un día (mm)", 0.0, 60.0, 0.0, 1.0, disabled=not simular)

    if simular:
        tmin, tmax, lluvia = s_tmin, s_tmax, s_lluvia
    else:
        tmin, tmax, lluvia = estacion.tmin_reciente, estacion.tmax_reciente, estacion.lluvia_reciente

    alertas = sorted((a for c in cultivos for a in evaluar(c, tmin, tmax, lluvia)),
                     key=lambda a: ORDEN_NIVEL[a.nivel])

    with zona_alertas:
        st.markdown("#### Tu alerta de hoy")
        if simular:
            st.markdown('<span class="ma-fuente simulacion">Simulación: no son datos reales</span>',
                        unsafe_allow_html=True)
        if not cultivos:
            st.info("Elige al menos un cultivo para ver tus alertas.")
        else:
            vistos = set()
            for alerta in alertas:  # la alerta más grave de cada cultivo
                if alerta.cultivo in vistos:
                    continue
                vistos.add(alerta.cultivo)
                st.markdown(tarjeta_alerta(alerta), unsafe_allow_html=True)

    st.markdown('<div class="ma-auspicio">Espacio auspiciador</div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Alertas
# --------------------------------------------------------------------------
with tab_alertas:
    if not cultivos:
        st.info("Elige al menos un cultivo en Inicio para ver tus alertas.")
    else:
        criticas = sum(a.nivel == "critico" for a in alertas)
        atencion = sum(a.nivel == "atencion" for a in alertas)
        st.markdown(f"**{criticas} crítica(s) · {atencion} de atención** · "
                    f"estación {estacion.nombre}")
        if simular:
            st.markdown('<span class="ma-fuente simulacion">Simulación: no son datos reales</span>',
                        unsafe_allow_html=True)
        for alerta in alertas:
            st.markdown(tarjeta_alerta(alerta), unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Mis cultivos (fichas)
# --------------------------------------------------------------------------
with tab_cultivos:
    elegido = st.selectbox("Elige un cultivo", list(FICHAS),
                           format_func=lambda k: f"{FICHAS[k].nombre} · {FICHAS[k].grupo}")
    ficha = FICHAS[elegido]
    cuidados = "".join(f"<li>{esc(c)}</li>" for c in ficha.cuidados)
    sin_limite = "sin límite definido"
    calor = (f"{numero_chileno(ficha.calor_sobre_c)} °C o más"
             if ficha.calor_sobre_c is not None else sin_limite)
    hongos = (f"{numero_chileno(ficha.lluvia_hongos_mm, 0)} mm o más en un día"
              if ficha.lluvia_hongos_mm is not None else sin_limite)
    st.markdown(
        f'<div class="ma-card"><h4>{esc(ficha.nombre)}</h4>'
        f'<p class="ma-sub">Cuidados básicos</p><ul class="ma-lista">{cuidados}</ul>'
        f'<p class="ma-sub">Límites que usa MeteoAgro</p><div class="ma-grid">'
        + dato("Helada", f"{numero_chileno(ficha.helada_bajo_c)} °C o menos")
        + dato("Calor", calor)
        + dato("Lluvia y hongos", hongos)
        + '</div></div>',
        unsafe_allow_html=True)
    st.caption(f"Fuente de los límites: {ficha.fuente}")
    st.caption("Las estaciones miden la temperatura del aire y las flores pueden estar más "
               "frías: conviene actuar antes de llegar al límite.")

# --------------------------------------------------------------------------
# Pregúntale (próximamente: chat con inteligencia artificial)
# --------------------------------------------------------------------------
def respuesta_helada() -> str:
    """Respuesta de ejemplo armada con las reglas y los datos de la estación (sin IA)."""
    if not cultivos:
        return "Elige tus cultivos en Inicio y te digo si hay riesgo de helada."
    if tmin is None:
        return f"La estación {estacion.nombre} no tiene la temperatura mínima en este momento."
    en_riesgo = [FICHAS[c].nombre for c in cultivos if tmin <= FICHAS[c].helada_bajo_c]
    texto = (f"En la estación {estacion.nombre}, la mínima "
             f"{'simulada' if simular else 'reciente'} es {numero_chileno(tmin)} °C. ")
    if en_riesgo:
        texto += (f"Eso es riesgo de helada para: {', '.join(en_riesgo)}. Si hay flores, brotes o "
                  "plantas chicas, usa riego por aspersión o cúbrelas.")
    else:
        nombres = ", ".join(FICHAS[c].nombre for c in cultivos)
        texto += f"Está sobre el límite de helada de tus cultivos ({nombres}), así que no hay riesgo."
    return texto + " Cuando MeteoAgro tenga el pronóstico de la DMC, te avisará antes de la helada."


with tab_pregunta:
    st.markdown('<span class="ma-fuente guardado">Próximamente</span>', unsafe_allow_html=True)
    st.markdown("**Pregúntale a MeteoAgro con tus palabras.** Pronto vas a poder escribir dudas "
                "como “¿Riego hoy mis tomates?” y recibir una respuesta simple, con los datos "
                "de tu estación.")
    st.caption("Vista previa: esta respuesta la arma MeteoAgro con sus reglas y los datos de "
               "la estación. Todavía no es inteligencia artificial.")
    with st.chat_message("user"):
        st.write("¿Hay riesgo de helada para mis cultivos?")
    with st.chat_message("assistant"):
        st.write(respuesta_helada())
    st.text_input("Escribe tu pregunta", placeholder="Disponible próximamente", disabled=True)

# --------------------------------------------------------------------------
# Perfil
# --------------------------------------------------------------------------
with tab_perfil:
    st.button("Entrar con Google (próximamente)", disabled=True)
    nombres = ", ".join(FICHAS[c].nombre for c in cultivos) or "ninguno todavía"
    st.markdown(f"**Tus cultivos:** {nombres}")
    st.caption("En la versión final, tu perfil guardará tu historial y tus cultivos "
               "en todos tus dispositivos.")

st.markdown('<div class="ma-pie">Fuente: Dirección Meteorológica de Chile (DMC). '
            'Prototipo beta de MeteoAgro · Taller 4, sección 4.</div>',
            unsafe_allow_html=True)

"""
MeteoAgro (beta) - Lectura de datos de la Dirección Meteorológica de Chile (DMC).

Usa el servicio "Resumen diario de la red de estaciones automáticas" (GeoJSON):
    https://climatologia.meteochile.gob.cl/application/geoservicios/getEmaResumenDiarioGeo

Dos formas de obtener los datos:
  - En vivo: con el correo y la API key de la DMC.
  - Datos guardados: el archivo datos/dmc_resumen_diario.json (consulta real del
    10-11-2026). Sirve para mostrar la app sin internet.

Lo que aprendimos de la respuesta real (10-11-2026):
  - Los nombres vienen con tildes rotas ("CuricÃ³"): se arreglan con arreglar_tildes().
  - Algunos números vienen como texto con coma de miles ("1,004.6").
  - Cuando no hay dato, el campo viene vacío ("") o como null.
  - El campo de la mínima de ayer se llama "temperaturaMinimaHAyer" (con una H de más).
  - "Hoy" y "ayer" son días en hora UTC (el día parte a las 21:00 de Chile en verano).
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

BASE = "https://climatologia.meteochile.gob.cl/application/"
ARCHIVO_DEMO = Path(__file__).parent / "datos" / "dmc_resumen_diario.json"


class ErrorDMC(Exception):
    """Problema al pedir o leer los datos de la DMC."""


# ---------------------------------------------------------------------------
# Limpieza de datos
# ---------------------------------------------------------------------------
def arreglar_tildes(texto):
    """La DMC manda 'CuricÃ³' en vez de 'Curicó'. Esto lo corrige."""
    if not isinstance(texto, str):
        return texto
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def a_numero(valor) -> Optional[float]:
    """Convierte 17.7, '1,004.6', '' o None en un número (o None si no hay dato)."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", "")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _minimo(*valores):
    numeros = [v for v in valores if v is not None]
    return min(numeros) if numeros else None


def _maximo(*valores):
    numeros = [v for v in valores if v is not None]
    return max(numeros) if numeros else None


# ---------------------------------------------------------------------------
# Estaciones
# ---------------------------------------------------------------------------
@dataclass
class Estacion:
    codigo: str
    nombre: str
    comuna: str
    region: str
    lat: float
    lon: float
    temperatura: Optional[float]
    humedad: Optional[float]
    tmin_hoy: Optional[float]
    tmax_hoy: Optional[float]
    tmin_ayer: Optional[float]
    tmax_ayer: Optional[float]
    lluvia_hoy: Optional[float]
    lluvia_ayer: Optional[float]
    actualizado_utc: Optional[datetime]

    @property
    def tmin_reciente(self) -> Optional[float]:
        """Temperatura más baja entre 'hoy' y 'ayer' (cubre la última noche)."""
        return _minimo(self.tmin_hoy, self.tmin_ayer)

    @property
    def tmax_reciente(self) -> Optional[float]:
        return _maximo(self.tmax_hoy, self.tmax_ayer)

    @property
    def lluvia_reciente(self) -> Optional[float]:
        """Lluvia del día con más agua entre 'hoy' y 'ayer' (mm en un día)."""
        return _maximo(self.lluvia_hoy, self.lluvia_ayer)

    @property
    def tiene_datos(self) -> bool:
        return self.temperatura is not None or self.tmin_reciente is not None


def _leer_fecha(texto) -> Optional[datetime]:
    try:
        return datetime.strptime(str(texto).strip(), "%d-%m-%Y %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def leer_estaciones(geojson: dict) -> list[Estacion]:
    """Transforma el GeoJSON de la DMC en una lista de estaciones limpias."""
    if not isinstance(geojson, dict) or "features" not in geojson:
        raise ErrorDMC("La respuesta de la DMC no trae estaciones.")
    estaciones = []
    for feature in geojson["features"]:
        p = feature.get("properties", {})
        lat, lon = a_numero(p.get("latitud")), a_numero(p.get("longitud"))
        if lat is None or lon is None:
            continue
        estaciones.append(Estacion(
            codigo=str(p.get("codigoNacional", "")),
            nombre=arreglar_tildes(p.get("nombreEstacion", "")),
            comuna=arreglar_tildes(p.get("comuna", "") or ""),
            region=arreglar_tildes(p.get("nombreRegion", "") or ""),
            lat=lat,
            lon=lon,
            temperatura=a_numero(p.get("temperatura")),
            humedad=a_numero(p.get("humedad")),
            tmin_hoy=a_numero(p.get("temperaturaMinimaHoy")),
            tmax_hoy=a_numero(p.get("temperaturaMaximaHoy")),
            tmin_ayer=a_numero(p.get("temperaturaMinimaHAyer", p.get("temperaturaMinimaAyer"))),
            tmax_ayer=a_numero(p.get("temperaturaMaximaAyer")),
            lluvia_hoy=a_numero(p.get("aguaCaidaHoy")),
            lluvia_ayer=a_numero(p.get("aguaCaidaAyer")),
            actualizado_utc=_leer_fecha(p.get("fechaCreacion", "")),
        ))
    return estaciones


def distancia_km(lat1, lon1, lat2, lon2) -> float:
    """Distancia en km entre dos puntos (fórmula de Haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def mas_cercana(estaciones: list[Estacion], lat: float, lon: float) -> tuple[Estacion, float]:
    """Estación con datos más cercana al punto, y su distancia en km."""
    con_datos = [e for e in estaciones if e.tiene_datos]
    if not con_datos:
        raise ErrorDMC("Ninguna estación trae datos en este momento.")
    mejor = min(con_datos, key=lambda e: distancia_km(lat, lon, e.lat, e.lon))
    return mejor, distancia_km(lat, lon, mejor.lat, mejor.lon)


# ---------------------------------------------------------------------------
# Obtener los datos
# ---------------------------------------------------------------------------
def descargar_resumen(usuario: str, token: str, timeout: int = 30) -> dict:
    """Pide el resumen diario en vivo a la DMC."""
    parametros = urllib.parse.urlencode({"usuario": usuario, "token": token})
    url = f"{BASE}geoservicios/getEmaResumenDiarioGeo?{parametros}"
    solicitud = urllib.request.Request(url, headers={"User-Agent": "MeteoAgro/0.2"})
    try:
        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        raise ErrorDMC(f"La DMC respondió con error {error.code}.") from error
    except urllib.error.URLError as error:
        raise ErrorDMC(f"No hay conexión con la DMC ({error.reason}).") from error
    except json.JSONDecodeError as error:
        raise ErrorDMC("La DMC respondió algo que no es JSON.") from error
    if isinstance(datos, dict) and "features" not in datos:
        raise ErrorDMC(datos.get("mensaje", "La DMC no entregó estaciones."))
    return datos


def cargar_guardados() -> dict:
    """Lee la consulta real guardada en datos/dmc_resumen_diario.json."""
    with open(ARCHIVO_DEMO, encoding="utf-8") as archivo:
        return json.load(archivo)


# ---------------------------------------------------------------------------
# Datos de las últimas 12 horas de una estación
# ---------------------------------------------------------------------------
def descargar_recientes(usuario: str, token: str, codigo: str, timeout: int = 30) -> dict:
    """Pide a la DMC las mediciones de las últimas 12 horas de una estación.

    Formato real (consulta del 10-11-2026): datosEstaciones.datos es una lista de
    unas 700 mediciones (casi una por minuto). Cada una trae "momento" en hora UTC
    y valores como texto con su unidad: "20.1 °C", "69 %", "3.3 kt".
    """
    parametros = urllib.parse.urlencode({"usuario": usuario, "token": token})
    url = f"{BASE}servicios/getDatosRecientesEma/{codigo}?{parametros}"
    solicitud = urllib.request.Request(url, headers={"User-Agent": "MeteoAgro/0.2"})
    try:
        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        raise ErrorDMC(f"La DMC respondió con error {error.code}.") from error
    except urllib.error.URLError as error:
        raise ErrorDMC(f"No hay conexión con la DMC ({error.reason}).") from error
    except json.JSONDecodeError as error:
        raise ErrorDMC("La DMC respondió algo que no es JSON.") from error
    if not isinstance(datos, dict) or "datosEstaciones" not in datos:
        mensaje = datos.get("mensaje") if isinstance(datos, dict) else None
        raise ErrorDMC(mensaje or "La DMC no entregó datos recientes.")
    return datos


def _valor(texto) -> Optional[float]:
    """'20.1 °C' -> 20.1 ; '3.3 kt' -> 3.3 ; None -> None."""
    if texto is None:
        return None
    return a_numero(str(texto).strip().split(" ")[0])


def _a_chile(fecha_utc: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return fecha_utc.astimezone(ZoneInfo("America/Santiago"))
    except Exception:
        return fecha_utc.astimezone(timezone(timedelta(hours=-3)))


def leer_recientes(datos: dict) -> list[dict]:
    """Convierte la respuesta en una lista ordenada de mediciones en hora de Chile."""
    registros = (datos.get("datosEstaciones") or {}).get("datos") or []
    filas = []
    for r in registros:
        try:
            momento = datetime.strptime(str(r.get("momento", "")), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        viento_kt = _valor(r.get("fuerzaDelVientoPromedio10Minutos"))
        filas.append({
            "hora": _a_chile(momento.replace(tzinfo=timezone.utc)).replace(tzinfo=None),
            "temperatura": _valor(r.get("temperatura")),
            "rocio": _valor(r.get("puntoDeRocio")),
            "humedad": _valor(r.get("humedadRelativa")),
            "viento_kmh": None if viento_kt is None else round(viento_kt * 1.852, 1),
        })
    filas.sort(key=lambda f: f["hora"])
    return filas


# ---------------------------------------------------------------------------
# Formato para mostrar
# ---------------------------------------------------------------------------
def hora_chile(fecha_utc: Optional[datetime]) -> str:
    """Convierte la hora UTC de la DMC a hora de Chile, como '10-11-2026, 01:10'."""
    if fecha_utc is None:
        return "sin hora"
    try:
        from zoneinfo import ZoneInfo
        local = fecha_utc.astimezone(ZoneInfo("America/Santiago"))
    except Exception:  # sin base de zonas horarias: horario de verano de Chile
        local = fecha_utc.astimezone(timezone(timedelta(hours=-3)))
    return local.strftime("%d-%m-%Y, %H:%M")


def numero_chileno(valor: Optional[float], decimales: int = 1) -> str:
    """12.9 -> '12,9'."""
    if valor is None:
        return "sin dato"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

"""
MeteoAgro (beta) - Motor de reglas por cultivo.

Compara los datos del clima con los límites de cada cultivo y entrega una alerta
simple con la acción a tomar.

Origen de los límites:
  - Palto, vid y trigo: valores de referencia del primer prototipo, TODAVÍA SIN
    VALIDAR. Hay que contrastarlos con boletines de INIA.
  - Cerezo, almendro y nogal (helada): temperatura máxima soportada 30 minutos con
    frutos recién cuajados (Saunier 1960, citado en Gil Albert 1986).
  - Cerezo (calor): sobre 30 °C en verano aumentan los frutos dobles
    (Beppu y Kataoka 1999, citado por SmartCherry).
  - Nogal (calor): golpe de sol con más de 30 °C, aire seco y mucho sol
    (INIA Intihuasi, publicado por Portal Frutícola, 2021).
  - Tomate: helada -2 °C y máximo de crecimiento 30 °C (Monardes 2009,
    Manual de cultivo de tomate, Universidad de Chile).
  - Lechuga y acelga (helada): "semi-resistentes": proteger cuando baja de
    unos -2 °C (Purdue Extension, 2005). Lechuga (calor): soporta hasta
    30 °C (Infoagro).
Las estaciones miden la temperatura del aire: las flores pueden estar más frías,
así que conviene actuar antes de llegar al límite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ficha:
    nombre: str
    grupo: str                          # "Frutales" u "Hortalizas"
    helada_bajo_c: float                # bajo o igual a esto: riesgo de helada
    calor_sobre_c: Optional[float]      # sobre o igual a esto: estrés por calor
    lluvia_hongos_mm: Optional[float]   # mm en un día que favorecen hongos
    cuidados: list = field(default_factory=list)
    fuente: str = ""
    calor_titulo: str = "Calor fuerte"
    calor_accion: str = "Refuerza el riego y evita trabajar en las horas de más sol."


FICHAS: dict[str, Ficha] = {
    # ---- Frutales ----------------------------------------------------------
    "palto": Ficha(
        nombre="Palto", grupo="Frutales",
        helada_bajo_c=1.0, calor_sobre_c=35.0, lluvia_hongos_mm=15.0,
        cuidados=[
            "Riega en forma regular, sin encharcar: sus raíces se asfixian con exceso de agua.",
            "Protege las raíces superficiales del sol con cobertura vegetal.",
            "Vigila la floración: las heladas tardías dañan flores y frutos chicos.",
        ],
        fuente="Valores de referencia del prototipo, por validar con INIA.",
    ),
    "vid": Ficha(
        nombre="Vid", grupo="Frutales",
        helada_bajo_c=0.0, calor_sobre_c=38.0, lluvia_hongos_mm=10.0,
        cuidados=[
            "En brotación (septiembre y octubre en Chile central) el riesgo de helada es alto.",
            "La humedad prolongada favorece oídio y botrytis.",
            "El exceso de calor en pinta puede quemar los racimos.",
        ],
        fuente="Valores de referencia del prototipo, por validar con INIA.",
    ),
    "cerezo": Ficha(
        nombre="Cerezo", grupo="Frutales",
        helada_bajo_c=-1.1, calor_sobre_c=30.0, lluvia_hongos_mm=None,
        cuidados=[
            "Es muy sensible a las heladas desde la plena flor hasta el fruto recién cuajado.",
            "En verano, el calor sobre 30 °C puede causar frutos dobles la temporada siguiente.",
            "La lluvia cerca de la cosecha puede partir la fruta.",
        ],
        fuente=("Helada: Saunier (1960), citado en Gil Albert (1986). "
                "Calor: Beppu y Kataoka (1999), citado por SmartCherry."),
        calor_titulo="Calor y frutos dobles",
        calor_accion="Mantén el huerto bien regado; el calor en verano aumenta los frutos dobles del próximo año.",
    ),
    "almendro": Ficha(
        nombre="Almendro", grupo="Frutales",
        helada_bajo_c=-1.1, calor_sobre_c=None, lluvia_hongos_mm=None,
        cuidados=[
            "Florece temprano, a fines del invierno, por eso queda muy expuesto a heladas.",
            "En plena flor soporta hasta unos -2,7 °C; el fruto recién cuajado, solo -1,1 °C.",
        ],
        fuente="Helada: Saunier (1960), citado en Gil Albert (1986).",
    ),
    "nogal": Ficha(
        nombre="Nogal", grupo="Frutales",
        helada_bajo_c=-1.1, calor_sobre_c=30.0, lluvia_hongos_mm=None,
        cuidados=[
            "Sus flores y frutos recién formados se dañan con -1,1 °C.",
            "El golpe de sol aparece con más de 30 °C, aire seco y mucho sol por más de 3 horas.",
        ],
        fuente=("Helada: Saunier (1960), citado en Gil Albert (1986). "
                "Golpe de sol: INIA Intihuasi (2021)."),
        calor_titulo="Riesgo de golpe de sol",
        calor_accion="Si además el aire está seco y hay mucho sol, riega bien y protege la fruta expuesta.",
    ),
    # ---- Cultivos anuales y hortalizas -------------------------------------
    "trigo": Ficha(
        nombre="Trigo", grupo="Cultivos y hortalizas",
        helada_bajo_c=-2.0, calor_sobre_c=32.0, lluvia_hongos_mm=20.0,
        cuidados=[
            "La lluvia excesiva en el llenado del grano favorece royas y fusarium.",
            "Un golpe de calor en floración reduce el peso del grano.",
        ],
        fuente="Valores de referencia del prototipo, por validar con INIA.",
    ),
    "tomate": Ficha(
        nombre="Tomate", grupo="Cultivos y hortalizas",
        helada_bajo_c=-2.0, calor_sobre_c=30.0, lluvia_hongos_mm=None,
        cuidados=[
            "Necesita calor: crece desde los 10 °C y su óptimo está entre 20 y 24 °C.",
            "La floración y la cuaja son las etapas más sensibles a las heladas.",
            "Sobre 30 °C deja de crecer bien.",
        ],
        fuente="Monardes (2009), Manual de cultivo de tomate, Universidad de Chile.",
    ),
    "lechuga": Ficha(
        nombre="Lechuga", grupo="Cultivos y hortalizas",
        helada_bajo_c=-2.0, calor_sobre_c=30.0, lluvia_hongos_mm=None,
        cuidados=[
            "Tolera heladas suaves; protégela si baja de unos -2 °C.",
            "Soporta peor el calor que el frío: con calor se espiga (sube a flor) y pierde calidad.",
        ],
        fuente="Helada: Purdue Extension (2005). Calor: Infoagro.",
        calor_titulo="Calor y espigado",
        calor_accion="Riega temprano o al atardecer y cosecha las que estén listas antes de que se espiguen.",
    ),
    "acelga": Ficha(
        nombre="Acelga", grupo="Cultivos y hortalizas",
        helada_bajo_c=-2.0, calor_sobre_c=None, lluvia_hongos_mm=None,
        cuidados=[
            "Tolera heladas suaves; protégela si baja de unos -2 °C.",
            "Se cosecha hoja por hoja durante varios meses.",
        ],
        fuente="Helada: Purdue Extension (2005).",
    ),
}

ORDEN_NIVEL = {"critico": 0, "atencion": 1, "ok": 2}


@dataclass
class Alerta:
    cultivo: str
    nivel: str      # "critico" | "atencion" | "ok"
    titulo: str
    detalle: str
    accion: str


def _n(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def evaluar(cultivo_id: str, tmin: Optional[float], tmax: Optional[float],
            lluvia_mm: Optional[float]) -> list[Alerta]:
    """Devuelve las alertas de un cultivo para los datos entregados."""
    f = FICHAS[cultivo_id]
    alertas = []

    if tmin is not None and tmin <= f.helada_bajo_c:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="critico", titulo=f"Riesgo de helada · {f.nombre}",
            detalle=f"La mínima llegó a {_n(tmin)} °C (límite {_n(f.helada_bajo_c)} °C).",
            accion="Si hay flores, brotes o plantas chicas, usa riego por aspersión o cúbrelas.",
        ))

    if f.calor_sobre_c is not None and tmax is not None and tmax >= f.calor_sobre_c:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"{f.calor_titulo} · {f.nombre}",
            detalle=f"La máxima llegó a {_n(tmax)} °C (límite {_n(f.calor_sobre_c)} °C).",
            accion=f.calor_accion,
        ))

    if f.lluvia_hongos_mm is not None and lluvia_mm is not None and lluvia_mm >= f.lluvia_hongos_mm:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"Riesgo de hongos · {f.nombre}",
            detalle=f"Cayeron {_n(lluvia_mm)} mm en un día (límite {_n(f.lluvia_hongos_mm)} mm).",
            accion="Revisa hojas y frutos, y evalúa una aplicación preventiva si corresponde.",
        ))

    if not alertas:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="ok", titulo=f"Sin alertas · {f.nombre}",
            detalle="Con los datos de la estación no hay riesgos para este cultivo.",
            accion="Sigue con tus cuidados normales.",
        ))
    return alertas
