"""
MeteoAgro - Revisar la API key de la DMC (versión 3)
====================================================

La versión anterior avisó que tu key tenía "2 caracteres raros". Esta versión:
  1. Te dice qué son esos caracteres (por ejemplo, un espacio invisible que se
     coló al copiar).
  2. Si son invisibles, prueba también la key sin ellos.
  3. Puede leer la key desde un archivo de texto llamado apikey.txt, para no
     tener que pegarla en PowerShell.

Cómo usarla con el archivo (recomendado):
  - Abre el Bloc de notas, pega SOLO tu API key y guarda el archivo con el
    nombre apikey.txt en esta misma carpeta.
  - En PowerShell, dentro de esta carpeta:  python probar_token_dmc.py
  - Cuando termines, borra apikey.txt (es tu clave personal).
"""

import getpass
import json
import os
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://climatologia.meteochile.gob.cl/application/"
ESTACION_CURICO = "340031"  # General Freire, Curicó Ad.
ARCHIVO_KEY = "apikey.txt"


def es_invisible(c):
    """Espacios, saltos de línea y caracteres de control que no se ven."""
    categoria = unicodedata.category(c)
    return categoria.startswith("C") or categoria.startswith("Z")


def nombre_caracter(c):
    return unicodedata.name(c, f"código U+{ord(c):04X}")


def revisar_key(token):
    print(f"   Tu API key tiene {len(token)} caracteres.")
    if len(token) > 8:
        print(f"   Empieza con '{token[:4]}' y termina con '{token[-4:]}'.")
    raros = [(i, c) for i, c in enumerate(token, 1) if not (c.isascii() and c.isalnum())]
    if not raros:
        print("   Solo tiene letras y números: se ve bien copiada.")
    for posicion, c in raros:
        if es_invisible(c):
            print(f"   - Carácter {posicion}: INVISIBLE ({nombre_caracter(c)}). "
                  "Esto se coló al copiar y no debería estar.")
        else:
            print(f"   - Carácter {posicion}: símbolo visible ({nombre_caracter(c)}). "
                  "Revisa que también esté en la key del portal.")


def pedir(usuario, token, codificar=True, ruta=None):
    """Pide datos a la DMC. Devuelve (funcionó, mensaje, datos)."""
    ruta = ruta or f"servicios/getDatosRecientesEma/{ESTACION_CURICO}"
    if codificar:
        parametros = urllib.parse.urlencode({"usuario": usuario, "token": token})
    else:  # tal cual, sin convertir "=" en "%3D" (como lo manda un navegador)
        parametros = f"usuario={usuario}&token={token}"
    url = f"{BASE}{ruta}?{parametros}"
    solicitud = urllib.request.Request(url, headers={"User-Agent": "MeteoAgro/0.2"})
    try:
        with urllib.request.urlopen(solicitud, timeout=60) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        return False, f"Error {error.code} de la DMC ({error.reason}).", None
    except urllib.error.URLError as error:
        return False, f"Sin conexión con la DMC ({error.reason}).", None
    except json.JSONDecodeError:
        return False, "La DMC respondió algo que no es JSON.", None
    if isinstance(datos, dict) and "mensaje" in datos and len(datos) <= 3:
        return False, datos["mensaje"], None
    return True, "", datos


def probar_resumen(usuario, token):
    """El resumen diario es lo que usa la app en vivo. ¿Funciona con esta key?"""
    print("\nProbando el resumen diario (lo que usa la app en vivo)...")
    funciono, mensaje, datos = pedir(usuario, token, ruta="geoservicios/getEmaResumenDiarioGeo")
    if funciono and isinstance(datos, dict) and datos.get("features"):
        print(f"   FUNCIONA: llegaron {len(datos['features'])} estaciones.")
        print("   La app con datos en vivo puede usar esta key.")
    else:
        print(f"   No funcionó: \"{mensaje}\"")


def main():
    print("=" * 60)
    print(" MeteoAgro - Revisar la API key de la DMC (versión 3)")
    print("=" * 60)
    usuario = input("Escribe tu correo de la DMC y aprieta Enter: ").strip()

    if os.path.exists(ARCHIVO_KEY):
        with open(ARCHIVO_KEY, encoding="utf-8-sig") as archivo:
            token = archivo.read().strip()
        print(f"Leí la API key desde {ARCHIVO_KEY}.")
    else:
        print("Pega tu API key con CLIC DERECHO y aprieta Enter (no se va a ver).")
        token = getpass.getpass("API key: ").strip()

    if not usuario or not token:
        print("Falta el correo o la API key. Vuelve a correr el script.")
        return

    print()
    revisar_key(token)

    probar_resumen(usuario, token)

    intentos = [("tal como la pegaste", token, True),
                ("sin codificar los signos = (como un navegador)", token, False)]
    limpia = "".join(c for c in token if not es_invisible(c))
    if limpia != token:
        intentos.append(("sin los caracteres invisibles", limpia, True))

    for descripcion, clave, codificar in intentos:
        print(f"\nDatos recientes de Curicó, con la key {descripcion}...")
        funciono, mensaje, datos = pedir(usuario, clave, codificar=codificar)
        if funciono:
            with open("dmc_datos_recientes.json", "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
            print("   FUNCIONÓ. Guardé la respuesta en dmc_datos_recientes.json.")
            if clave != token:
                print("   El problema eran los caracteres invisibles: copia la key de nuevo,")
                print("   con cuidado de no seleccionar espacios antes ni después.")
            print("   Mándale a Claude el archivo dmc_datos_recientes.json.")
            return
        print(f"   La DMC respondió: \"{mensaje}\"")

    print("\nNo funcionó. Mándale a Claude una foto de esta pantalla")
    print("(tapa la parte que muestra cómo empieza y termina tu key).")


if __name__ == "__main__":
    main()
