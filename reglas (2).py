"""
MeteoAgro (beta) - Motor de reglas por cultivo.

Compara los datos del clima con los límites de cada cultivo y entrega una alerta
simple con la acción a tomar.

Origen de los límites:
  - Frutales (helada): temperatura máxima soportada durante 30 minutos con frutos
    recién cuajados, la etapa más sensible (Saunier 1960, citado en Gil Albert 1986).
  - Hortalizas (helada): grupos de resistencia al frío de Purdue Extension (2005):
      sensibles -> se dañan con helada suave (0 °C)
      semirresistentes -> proteger si baja de unos -2 °C ("mid- to upper 20s °F")
      resistentes -> proteger si baja de unos -5 °C ("low 20s °F")
  - Cerezo (calor): sobre 30 °C en verano aumentan los frutos dobles
    (Beppu y Kataoka 1999, citado por SmartCherry).
  - Nogal (calor): golpe de sol con más de 30 °C, aire seco y mucho sol
    (INIA Intihuasi, publicado por Portal Frutícola, 2021).
  - Tomate (calor y crecimiento): Monardes (2009), Manual de cultivo de tomate,
    Universidad de Chile. Lechuga (calor): soporta hasta 30 °C (Infoagro).
  - Palto y trigo, y el calor y la lluvia de la vid: valores de referencia del
    primer prototipo, TODAVÍA SIN VALIDAR (contrastar con boletines de INIA).
Las estaciones miden la temperatura del aire: las flores y las plantas pueden
estar más frías, así que conviene actuar antes de llegar al límite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

FRUTALES = "Frutales"
HORTALIZAS = "Hortalizas y cultivos"

FUENTE_FRUTALES = "Helada: Saunier (1960), citado en Gil Albert (1986)."
FUENTE_PURDUE = "Helada: Purdue Extension (2005), Cold Temperature Tolerance of Vegetables."
FUENTE_PROTOTIPO = "Valores de referencia del prototipo, por validar con INIA."


@dataclass
class Ficha:
    nombre: str
    grupo: str
    helada_bajo_c: float                # bajo o igual a esto: riesgo de helada
    calor_sobre_c: Optional[float]      # sobre o igual a esto: estrés por calor
    lluvia_hongos_mm: Optional[float]   # mm en un día que favorecen hongos
    cuidados: list = field(default_factory=list)
    fuente: str = ""
    calor_titulo: str = "Calor fuerte"
    calor_accion: str = "Refuerza el riego y evita trabajar en las horas de más sol."


def _n(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _frutal(nombre: str, plena_flor: float, fruto_joven: float, **extra) -> Ficha:
    """Frutal con los valores de la tabla de Saunier (1960)."""
    cuidados = [
        f"Lo más sensible al frío es el fruto recién cuajado: se daña con {_n(fruto_joven)} °C.",
        f"En plena flor soporta hasta {_n(plena_flor)} °C durante 30 minutos.",
    ] + extra.pop("cuidados_extra", [])
    return Ficha(nombre=nombre, grupo=FRUTALES, helada_bajo_c=fruto_joven,
                 calor_sobre_c=extra.pop("calor_sobre_c", None),
                 lluvia_hongos_mm=extra.pop("lluvia_hongos_mm", None),
                 cuidados=cuidados, fuente=extra.pop("fuente", FUENTE_FRUTALES), **extra)


SENSIBLE, SEMI, RESISTENTE = 0.0, -2.0, -5.0
_CUIDADOS_HORTALIZA = {
    SENSIBLE: ["Muy sensible a las heladas: protégelo o cosecha antes de una noche bajo 0 °C.",
               "Siémbralo cuando ya no haya riesgo de heladas en primavera."],
    SEMI: ["Tolera heladas suaves: protégelo si la temperatura baja de unos -2 °C."],
    RESISTENTE: ["Resiste heladas fuertes: protégelo solo si la temperatura se acerca a -5 °C."],
}


def _hortaliza(nombre: str, grupo_frio: float, **extra) -> Ficha:
    """Hortaliza clasificada según su resistencia al frío (Purdue Extension, 2005)."""
    cuidados = list(_CUIDADOS_HORTALIZA[grupo_frio]) + extra.pop("cuidados_extra", [])
    return Ficha(nombre=nombre, grupo=HORTALIZAS, helada_bajo_c=grupo_frio,
                 calor_sobre_c=extra.pop("calor_sobre_c", None),
                 lluvia_hongos_mm=extra.pop("lluvia_hongos_mm", None),
                 cuidados=cuidados, fuente=extra.pop("fuente", FUENTE_PURDUE), **extra)


FICHAS: dict[str, Ficha] = {
    # ---- Frutales -----------------------------------------------------------
    "almendro": _frutal("Almendro", -2.7, -1.1, cuidados_extra=[
        "Florece temprano, a fines del invierno, por eso queda muy expuesto a heladas."]),
    "cerezo": _frutal(
        "Cerezo", -2.2, -1.1, calor_sobre_c=30.0,
        cuidados_extra=["En verano, el calor sobre 30 °C puede causar frutos dobles la temporada siguiente.",
                        "La lluvia cerca de la cosecha puede partir la fruta."],
        fuente=FUENTE_FRUTALES + " Calor: Beppu y Kataoka (1999), citado por SmartCherry.",
        calor_titulo="Calor y frutos dobles",
        calor_accion="Mantén el huerto bien regado; el calor en verano aumenta los frutos dobles del próximo año."),
    "ciruelo": _frutal("Ciruelo", -2.8, -1.1, cuidados_extra=[
        "El ciruelo japonés es algo más sensible en plena flor (-2,2 °C)."]),
    "damasco": _frutal("Damasco", -2.2, -0.5),
    "durazno": _frutal("Durazno", -2.5, -1.6),
    "manzano": _frutal("Manzano", -2.2, -1.6),
    "nogal": _frutal(
        "Nogal", -1.1, -1.1, calor_sobre_c=30.0,
        cuidados_extra=["El golpe de sol aparece con más de 30 °C, aire seco y mucho sol por más de 3 horas."],
        fuente=FUENTE_FRUTALES + " Golpe de sol: INIA Intihuasi (2021).",
        calor_titulo="Riesgo de golpe de sol",
        calor_accion="Si además el aire está seco y hay mucho sol, riega bien y protege la fruta expuesta."),
    "palto": Ficha(
        nombre="Palto", grupo=FRUTALES, helada_bajo_c=1.0, calor_sobre_c=35.0, lluvia_hongos_mm=15.0,
        cuidados=["Riega en forma regular, sin encharcar: sus raíces se asfixian con exceso de agua.",
                  "Protege las raíces superficiales del sol con cobertura vegetal.",
                  "Vigila la floración: las heladas tardías dañan flores y frutos chicos."],
        fuente=FUENTE_PROTOTIPO),
    "peral": _frutal("Peral", -1.7, -1.1, cuidados_extra=[
        "Las variedades más resistentes soportan hasta -2,2 °C en plena flor."]),
    "vid": _frutal(
        "Vid", -0.5, -0.5, calor_sobre_c=38.0, lluvia_hongos_mm=10.0,
        cuidados_extra=["En brotación (septiembre y octubre en Chile central) el riesgo de helada es alto.",
                        "La humedad prolongada favorece oídio y botrytis."],
        fuente=FUENTE_FRUTALES + " Calor y lluvia: " + FUENTE_PROTOTIPO.lower()),
    # ---- Hortalizas y cultivos ----------------------------------------------
    "acelga": _hortaliza("Acelga", SEMI, cuidados_extra=["Se cosecha hoja por hoja durante varios meses."]),
    "apio": _hortaliza("Apio", SEMI),
    "arveja": _hortaliza("Arveja", RESISTENTE),
    "betarraga": _hortaliza("Betarraga", SEMI),
    "brocoli": _hortaliza("Brócoli", RESISTENTE),
    "cebolla": _hortaliza("Cebolla", RESISTENTE),
    "choclo": _hortaliza("Choclo", SENSIBLE),
    "coliflor": _hortaliza("Coliflor", SEMI),
    "espinaca": _hortaliza("Espinaca", RESISTENTE),
    "lechuga": _hortaliza(
        "Lechuga", SEMI, calor_sobre_c=30.0,
        cuidados_extra=["Soporta peor el calor que el frío: con calor se espiga (sube a flor) y pierde calidad."],
        fuente=FUENTE_PURDUE + " Calor: Infoagro.",
        calor_titulo="Calor y espigado",
        calor_accion="Riega temprano o al atardecer y cosecha las que estén listas antes de que se espiguen."),
    "melon": _hortaliza("Melón", SENSIBLE),
    "papa": _hortaliza("Papa", SEMI),
    "pepino": _hortaliza("Pepino", SENSIBLE),
    "pimenton": _hortaliza("Pimentón", SENSIBLE),
    "poroto": _hortaliza("Poroto", SENSIBLE),
    "repollo": _hortaliza("Repollo", RESISTENTE),
    "sandia": _hortaliza("Sandía", SENSIBLE),
    "tomate": _hortaliza(
        "Tomate", SENSIBLE, calor_sobre_c=30.0,
        cuidados_extra=["Necesita calor: crece desde los 10 °C y su óptimo está entre 20 y 24 °C.",
                        "Sobre 30 °C deja de crecer bien."],
        fuente=FUENTE_PURDUE + " Calor y crecimiento: Monardes (2009), Manual de cultivo de tomate, U. de Chile."),
    "trigo": Ficha(
        nombre="Trigo", grupo=HORTALIZAS, helada_bajo_c=-2.0, calor_sobre_c=32.0, lluvia_hongos_mm=20.0,
        cuidados=["La lluvia excesiva en el llenado del grano favorece royas y fusarium.",
                  "Un golpe de calor en floración reduce el peso del grano."],
        fuente=FUENTE_PROTOTIPO),
    "zanahoria": _hortaliza("Zanahoria", SEMI),
    "zapallo": _hortaliza("Zapallo", SENSIBLE),
}

ORDEN_NIVEL = {"critico": 0, "atencion": 1, "ok": 2}


@dataclass
class Alerta:
    cultivo: str
    nivel: str      # "critico" | "atencion" | "ok"
    titulo: str
    detalle: str
    accion: str


def evaluar(cultivo_id: str, tmin: Optional[float], tmax: Optional[float],
            lluvia_mm: Optional[float], pronostico: bool = False) -> list[Alerta]:
    """Devuelve las alertas de un cultivo para los datos entregados.

    Con pronostico=True los textos hablan de lo que se espera ("se espera una
    mínima de...") en vez de lo que ya pasó ("la mínima llegó a...").
    """
    f = FICHAS[cultivo_id]
    alertas = []
    minima = "Se espera una mínima de" if pronostico else "La mínima llegó a"
    maxima = "Se espera una máxima de" if pronostico else "La máxima llegó a"
    lluvia = "Se esperan" if pronostico else "Cayeron"

    if tmin is not None and tmin <= f.helada_bajo_c:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="critico", titulo=f"Riesgo de helada · {f.nombre}",
            detalle=f"{minima} {_n(tmin)} °C (límite {_n(f.helada_bajo_c)} °C).",
            accion="Si hay flores, brotes o plantas chicas, usa riego por aspersión o cúbrelas.",
        ))

    if f.calor_sobre_c is not None and tmax is not None and tmax >= f.calor_sobre_c:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"{f.calor_titulo} · {f.nombre}",
            detalle=f"{maxima} {_n(tmax)} °C (límite {_n(f.calor_sobre_c)} °C).",
            accion=f.calor_accion,
        ))

    if f.lluvia_hongos_mm is not None and lluvia_mm is not None and lluvia_mm >= f.lluvia_hongos_mm:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"Riesgo de hongos · {f.nombre}",
            detalle=f"{lluvia} {_n(lluvia_mm)} mm en un día (límite {_n(f.lluvia_hongos_mm)} mm).",
            accion="Revisa hojas y frutos, y evalúa una aplicación preventiva si corresponde.",
        ))

    if not alertas:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="ok", titulo=f"Sin alertas · {f.nombre}",
            detalle="Con estos datos no hay riesgos para este cultivo.",
            accion="Sigue con tus cuidados normales.",
        ))
    return alertas
