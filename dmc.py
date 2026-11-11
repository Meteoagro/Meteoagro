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
