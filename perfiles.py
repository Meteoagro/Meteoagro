"""
MeteoAgro (beta) - Perfiles de usuario guardados en una hoja de Google Sheets.

Cada fila de la pestaña "usuarios" es una persona que entró con Google.
La usan la app (para guardar el perfil) y el envío automático de alertas.

Se conecta con una "cuenta de servicio" de Google Cloud. Sus credenciales
(un archivo JSON) se guardan como secreto, nunca en el código.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

COLUMNAS = ["email", "nombre", "region", "comuna", "lat", "lon", "cultivos",
            "alertas", "actualizado", "ultima_alerta"]
PESTANA = "usuarios"


def leer_credenciales(texto_o_dict) -> dict:
    """Acepta el JSON de la cuenta de servicio como texto o como diccionario."""
    if isinstance(texto_o_dict, str):
        return json.loads(texto_o_dict)
    return dict(texto_o_dict)


def abrir_hoja(credenciales: dict, id_hoja: str):
    """Abre la pestaña de usuarios; si no existe, la crea con sus columnas."""
    import gspread  # se importa aquí para que la app funcione aunque no esté configurada

    cliente = gspread.service_account_from_dict(credenciales)
    libro = cliente.open_by_key(id_hoja)
    try:
        hoja = libro.worksheet(PESTANA)
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(PESTANA, rows=1000, cols=len(COLUMNAS))
    if hoja.row_values(1) != COLUMNAS:
        hoja.update([COLUMNAS], "A1")
    return hoja


def leer_perfiles(hoja) -> list[dict]:
    """Todos los perfiles, como lista de diccionarios."""
    return [dict(fila) for fila in hoja.get_all_records(expected_headers=COLUMNAS)]


def buscar_perfil(hoja, email: str) -> Optional[dict]:
    email = email.strip().lower()
    for perfil in leer_perfiles(hoja):
        if str(perfil.get("email", "")).strip().lower() == email:
            return perfil
    return None


def ahora_chile() -> str:
    try:
        from zoneinfo import ZoneInfo
        hora = datetime.now(ZoneInfo("America/Santiago"))
    except Exception:
        hora = datetime.now(timezone(timedelta(hours=-3)))
    return hora.strftime("%Y-%m-%d %H:%M")


def guardar_perfil(hoja, perfil: dict) -> None:
    """Crea o actualiza la fila de esa persona (se busca por correo)."""
    perfil = dict(perfil)
    perfil["email"] = perfil["email"].strip().lower()
    perfil["actualizado"] = ahora_chile()
    correos = [c.strip().lower() for c in hoja.col_values(1)]
    if perfil["email"] in correos:
        numero_fila = correos.index(perfil["email"]) + 1
        anterior = dict(zip(COLUMNAS, hoja.row_values(numero_fila) + [""] * len(COLUMNAS)))
        perfil.setdefault("ultima_alerta", anterior.get("ultima_alerta", ""))
        fila = [perfil.get(c, "") for c in COLUMNAS]
        hoja.update([fila], f"A{numero_fila}")
    else:
        hoja.append_row([perfil.get(c, "") for c in COLUMNAS])


def marcar_alerta_enviada(hoja, email: str, fecha: str) -> None:
    """Anota el día de la última alerta, para no mandar dos el mismo día."""
    correos = [c.strip().lower() for c in hoja.col_values(1)]
    email = email.strip().lower()
    if email in correos:
        hoja.update_cell(correos.index(email) + 1, COLUMNAS.index("ultima_alerta") + 1, fecha)
