"""
MeteoAgro (beta) - Motor de reglas por cultivo.

Compara los datos del clima con umbrales de cada cultivo y entrega una alerta
simple con la acción a tomar.

IMPORTANTE: los umbrales son valores de referencia del primer prototipo.
Todavía NO están validados agronómicamente: hay que contrastarlos con los
boletines de INIA antes de usarlos con agricultores reales.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ficha:
    nombre: str
    helada_bajo_c: float        # bajo o igual a esto: riesgo de helada
    calor_sobre_c: float        # sobre o igual a esto: estrés por calor
    lluvia_hongos_mm: float     # mm en un día que favorecen hongos
    cuidados: list = field(default_factory=list)


FICHAS: dict[str, Ficha] = {
    "palto": Ficha(
        nombre="Palto",
        helada_bajo_c=1.0,
        calor_sobre_c=35.0,
        lluvia_hongos_mm=15.0,
        cuidados=[
            "Riega en forma regular, sin encharcar: sus raíces se asfixian con exceso de agua.",
            "Protege las raíces superficiales del sol con cobertura vegetal.",
            "Vigila la floración: las heladas tardías dañan flores y frutos chicos.",
        ],
    ),
    "vid": Ficha(
        nombre="Vid",
        helada_bajo_c=0.0,
        calor_sobre_c=38.0,
        lluvia_hongos_mm=10.0,
        cuidados=[
            "En brotación (septiembre y octubre en Chile central) el riesgo de helada es alto.",
            "La humedad prolongada favorece oídio y botrytis.",
            "El exceso de calor en pinta puede quemar los racimos.",
        ],
    ),
    "trigo": Ficha(
        nombre="Trigo",
        helada_bajo_c=-2.0,
        calor_sobre_c=32.0,
        lluvia_hongos_mm=20.0,
        cuidados=[
            "La lluvia excesiva en el llenado del grano favorece royas y fusarium.",
            "Un golpe de calor en floración reduce el peso del grano.",
        ],
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
            accion="Si hay flores o brotes, usa riego por aspersión o cubre las plantas.",
        ))

    if tmax is not None and tmax >= f.calor_sobre_c:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"Calor fuerte · {f.nombre}",
            detalle=f"La máxima llegó a {_n(tmax)} °C (límite {_n(f.calor_sobre_c)} °C).",
            accion="Refuerza el riego y evita trabajar en las horas de más sol.",
        ))

    if lluvia_mm is not None and lluvia_mm >= f.lluvia_hongos_mm:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="atencion", titulo=f"Riesgo de hongos · {f.nombre}",
            detalle=f"Cayeron {_n(lluvia_mm)} mm en un día (límite {_n(f.lluvia_hongos_mm)} mm).",
            accion="Revisa hojas y frutos, y evalúa una aplicación preventiva si corresponde.",
        ))

    if not alertas:
        alertas.append(Alerta(
            cultivo=f.nombre, nivel="ok", titulo=f"Sin alertas · {f.nombre}",
            detalle="Con los datos de la estación no hay riesgo de helada, calor ni hongos.",
            accion="Sigue con tus cuidados normales.",
        ))
    return alertas
