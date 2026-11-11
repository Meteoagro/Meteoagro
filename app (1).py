"""
MeteoAgro (beta) - App en Streamlit.

Cómo correrla (PowerShell, dentro de esta carpeta):
    python -m streamlit run app.py
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dmc import (ErrorDMC, cargar_guardados, descargar_recientes, descargar_resumen,
                 hora_chile, leer_estaciones, leer_recientes, mas_cercana, numero_chileno)
from reglas import FICHAS, ORDEN_NIVEL, evaluar

try:  # botón para usar el GPS del celular (componente opcional)
    from streamlit_geolocation import streamlit_geolocation
except Exception:
    streamlit_geolocation = None

st.set_page_config(page_title="MeteoAgro", page_icon="🌱", layout="centered")

REGION_POR_DEFECTO = "Metropolitana de Santiago"
COMUNA_POR_DEFECTO = "Santiago"
DISTANCIA_LEJANA_KM = 40
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


@st.cache_data(show_spinner=False)
def cargar_comunas() -> dict:
    """Todas las comunas de Chile por región, con su punto central aproximado."""
    with open(Path(__file__).parent / "datos" / "comunas.json", encoding="utf-8") as archivo:
        return json.load(archivo)["regiones"]


COMUNAS = cargar_comunas()


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
    st.markdown("**¿Dónde está tu campo?**")
    gps = None
    if streamlit_geolocation is not None:
        st.caption("Toca el ícono para usar la ubicación de tu celular, o elige tu comuna.")
        try:
            ubicacion = streamlit_geolocation()
        except Exception:
            ubicacion = None
        if (isinstance(ubicacion, dict) and ubicacion.get("latitude") is not None
                and ubicacion.get("longitude") is not None):
            gps = (float(ubicacion["latitude"]), float(ubicacion["longitude"]))
    usar_gps = gps is not None and st.toggle("Usar mi ubicación actual", value=True)

    regiones = list(COMUNAS)
    region_guardada = st.query_params.get("region", REGION_POR_DEFECTO)
    if region_guardada not in COMUNAS:
        region_guardada = REGION_POR_DEFECTO
    region = st.selectbox("Región", regiones, index=regiones.index(region_guardada),
                          disabled=usar_gps)
    nombres_comunas = [c[0] for c in COMUNAS[region]]
    comuna_guardada = st.query_params.get("comuna", COMUNA_POR_DEFECTO)
    indice = nombres_comunas.index(comuna_guardada) if comuna_guardada in nombres_comunas else 0
    comuna = st.selectbox("Comuna", nombres_comunas, index=indice, disabled=usar_gps)

    if usar_gps:
        lat, lon = gps
        lugar_texto = "tu ubicación actual"
    else:
        _, lat, lon = COMUNAS[region][nombres_comunas.index(comuna)]
        lugar_texto = comuna
        st.query_params["region"] = region      # así el link recuerda tu comuna
        st.query_params["comuna"] = comuna

    cultivos = st.multiselect("¿Qué cultivas?", list(FICHAS), default=["palto"],
                              format_func=lambda k: FICHAS[k].nombre,
                              placeholder="Elige uno o más cultivos")

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
        f'<p class="ma-sub">Estación DMC más cercana · a {numero_chileno(km)} km de '
        f'{esc(lugar_texto)}</p><div class="ma-grid">'
        + dato("Temperatura", con_unidad(estacion.temperatura, "°C"))
        + dato("Humedad", con_unidad(estacion.humedad, "%", 0))
        + dato("Mínima reciente", con_unidad(estacion.tmin_reciente, "°C"))
        + dato("Máxima reciente", con_unidad(estacion.tmax_reciente, "°C"))
        + dato("Lluvia reciente", con_unidad(estacion.lluvia_reciente, "mm"))
        + dato("Actualizado", actualizado)
        + '</div></div>',
        unsafe_allow_html=True)
    st.caption("“Reciente” = lo más extremo entre hoy y ayer en la estación.")
    if km > DISTANCIA_LEJANA_KM:
        st.info(f"La estación más cercana está a {numero_chileno(km, 0)} km: el clima en tu "
                "campo puede ser distinto. Úsalo como referencia.")

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
