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
