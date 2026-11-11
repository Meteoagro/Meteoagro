"""
MeteoAgro - Envío automático de alertas por correo.

GitHub Actions corre este script todos los días a las 18:00 de Chile
(ver .github/workflows/alertas.yml). Para cada persona que activó las alertas:
  1. Pide el pronóstico de mañana para su campo (Open-Meteo, gratis para uso
     no comercial, licencia CC BY 4.0).
  2. Compara la mínima, la máxima y la lluvia con los límites de sus cultivos.
  3. Si hay riesgo, le manda un correo con la acción a tomar y los datos de la
     estación de la DMC más cercana. Manda como máximo un correo al día.

Secretos que necesita (en GitHub: Settings > Secrets and variables > Actions):
  DMC_USUARIO, DMC_TOKEN        cuenta de la DMC
  GCP_SERVICE_ACCOUNT           JSON de la cuenta de servicio de Google
  SHEET_ID                      identificador de la hoja de perfiles
  GMAIL_USUARIO, GMAIL_CLAVE_APP  correo que envía y su "contraseña de aplicación"
Opcional: APP_URL (link de la app) y MODO:
  normal  revisa el pronóstico real y avisa solo si hay riesgo (lo de todos los días)
  prueba  hace todo igual pero NO envía correos: solo muestra en el registro qué mandaría
  demo    manda a todos un correo de prueba con una helada simulada (para mostrar la app)
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Optional

from dmc import ErrorDMC, descargar_resumen, leer_estaciones, mas_cercana, numero_chileno
from perfiles import abrir_hoja, ahora_chile, leer_credenciales, leer_perfiles, marcar_alerta_enviada
from reglas import FICHAS, ORDEN_NIVEL, evaluar

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def pronostico_manana(lat: float, lon: float) -> dict:
    """Mínima, máxima y lluvia pronosticadas para mañana (hora de Chile)."""
    parametros = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
        "timezone": "America/Santiago", "forecast_days": 2,
    })
    solicitud = urllib.request.Request(f"{OPEN_METEO}?{parametros}",
                                       headers={"User-Agent": "MeteoAgro/0.3"})
    with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
        diario = json.loads(respuesta.read().decode("utf-8"))["daily"]
    return {
        "fecha": diario["time"][1],
        "tmin": diario["temperature_2m_min"][1],
        "tmax": diario["temperature_2m_max"][1],
        "lluvia": diario["precipitation_sum"][1],
    }


def armar_correo(perfil: dict, pron: dict, alertas: list, estacion, km: Optional[float],
                 app_url: str) -> tuple[str, str]:
    """Devuelve (asunto, texto) del correo."""
    principal = alertas[0]
    riesgo = principal.titulo.split(" · ")[0]
    asunto = f"MeteoAgro: {riesgo} mañana para tu {principal.cultivo.lower()}"
    if len(alertas) > 1:
        asunto += f" (y {len(alertas) - 1} aviso{'s' if len(alertas) > 2 else ''} más)"
    nombre = str(perfil.get("nombre") or "").strip().split(" ")[0]
    lineas = [
        f"Hola {nombre}:" if nombre else "Hola:",
        "",
        f"Pronóstico para {perfil.get('comuna') or 'tu campo'} (mañana {pron['fecha']}): "
        f"mínima {numero_chileno(pron['tmin'])} °C, máxima {numero_chileno(pron['tmax'])} °C, "
        f"lluvia {numero_chileno(pron['lluvia'])} mm.",
        "",
    ]
    for a in alertas:
        lineas += [f"• {a.titulo}", f"  {a.detalle}", f"  Qué hacer: {a.accion}", ""]
    if estacion is not None:
        lineas.append(f"Estación de la DMC más cercana: {estacion.nombre}, a {numero_chileno(km)} km. "
                      f"Temperatura ahora: {numero_chileno(estacion.temperatura)} °C.")
    if app_url:
        lineas.append(f"Revisa el detalle en la app: {app_url}")
    lineas += [
        "",
        "Pronóstico: Open-Meteo.com (CC BY 4.0). Datos medidos: Dirección Meteorológica de Chile.",
        "Para dejar de recibir alertas, desactívalas en la pestaña Perfil de MeteoAgro.",
    ]
    return asunto, "\n".join(lineas)


def enviar_correo(usuario: str, clave: str, destino: str, asunto: str, texto: str) -> None:
    mensaje = EmailMessage()
    mensaje["From"] = f"MeteoAgro <{usuario}>"
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as servidor:
        servidor.login(usuario, clave)
        servidor.send_message(mensaje)


def main() -> int:
    modo = os.environ.get("MODO", "normal").strip().lower()
    modo_prueba, modo_demo = modo.startswith("prueba"), modo.startswith("demo")
    print(f"Modo: {'prueba (no envía)' if modo_prueba else 'demo (helada simulada)' if modo_demo else 'normal'}")
    app_url = os.environ.get("APP_URL", "")
    hoy = ahora_chile()[:10]

    hoja = abrir_hoja(leer_credenciales(os.environ["GCP_SERVICE_ACCOUNT"]), os.environ["SHEET_ID"])
    perfiles = [p for p in leer_perfiles(hoja) if str(p.get("alertas", "")).strip().lower() == "sí"]
    print(f"Personas con alertas activas: {len(perfiles)}")

    estaciones = []
    try:
        estaciones = leer_estaciones(descargar_resumen(os.environ.get("DMC_USUARIO", ""),
                                                       os.environ.get("DMC_TOKEN", "")))
    except ErrorDMC as error:
        print(f"Aviso: no se pudieron leer los datos de la DMC ({error}). Sigo solo con el pronóstico.")

    enviados = 0
    for perfil in perfiles:
        email = str(perfil.get("email", "")).strip()
        if not modo_demo and str(perfil.get("ultima_alerta", ""))[:10] == hoy:
            print(f"- {email}: ya recibió una alerta hoy.")
            continue
        try:
            lat, lon = float(perfil["lat"]), float(perfil["lon"])
        except (KeyError, TypeError, ValueError):
            print(f"- {email}: el perfil no tiene ubicación válida.")
            continue
        cultivos = [c for c in str(perfil.get("cultivos", "")).split(",") if c in FICHAS]
        if not cultivos:
            continue
        try:
            pron = pronostico_manana(lat, lon)
        except Exception as error:  # sin pronóstico no se puede avisar antes
            print(f"- {email}: no se pudo leer el pronóstico ({error}).")
            continue
        if modo_demo:
            pron = {**pron, "tmin": -2.0}

        alertas = [a for c in cultivos
                   for a in evaluar(c, pron["tmin"], pron["tmax"], pron["lluvia"], pronostico=True)
                   if a.nivel != "ok"]
        if not alertas:
            print(f"- {email}: sin riesgos para mañana.")
            continue
        alertas.sort(key=lambda a: ORDEN_NIVEL[a.nivel])

        estacion, km = (mas_cercana(estaciones, lat, lon) if estaciones else (None, None))
        asunto, texto = armar_correo(perfil, pron, alertas, estacion, km, app_url)
        if modo_demo:
            asunto = "[Prueba] " + asunto
            texto = ("ESTE ES UN CORREO DE PRUEBA: la mínima de -2 °C es simulada, "
                     "no es el pronóstico real.\n\n" + texto)
        if modo_prueba:
            print(f"- {email}: [MODO PRUEBA] se enviaría «{asunto}»\n{texto}\n")
            continue
        enviar_correo(os.environ["GMAIL_USUARIO"], os.environ["GMAIL_CLAVE_APP"], email, asunto, texto)
        if not modo_demo:
            marcar_alerta_enviada(hoja, email, ahora_chile())
        enviados += 1
        print(f"- {email}: alerta enviada.")

    print(f"Listo. Correos enviados: {enviados}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
