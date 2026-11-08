
"""
Configuración del entorno del proyecto y de los directorios.

Es el ÚNICO lugar que carga el .env y resuelve rutas: el resto de los módulos
importa desde acá y no usa load_dotenv ni arma rutas por su cuenta.
"""
import os  # para acceder a las variables de entorno del sistema operativo
import warnings  # avisos por stderr (no se puede usar el logger: utilidades_logs importa este módulo)
from pathlib import Path  # manipular rutas de forma orientada a objetos e independiente del SO

from dotenv import load_dotenv  # lee las variables clave=valor de un .env y las asigna al entorno del proceso

MARCADOR_RAIZ = "alembic.ini"  # archivo versionado que solo existe en la raíz del proyecto


def _buscar_raiz_proyecto() -> Path:
    """Sube desde este archivo hasta encontrar la carpeta que contiene el marcador."""
    inicio = Path(__file__).resolve()  # ruta absoluta y real de este archivo
    for carpeta in inicio.parents:  # recorre las carpetas superiores: padre, abuelo, etc.
        if (carpeta / MARCADOR_RAIZ).is_file():  # ¿esta carpeta contiene el marcador?
            return carpeta
    raise FileNotFoundError(
        f"No se encontró la raíz del proyecto: ninguna carpeta sobre {inicio} contiene '{MARCADOR_RAIZ}'."
    )


RAIZ_PROYECTO = _buscar_raiz_proyecto()

ARCHIVO_ENV = RAIZ_PROYECTO / ".env"
if not ARCHIVO_ENV.is_file():
    # No se lanza error: en Docker/CI las variables pueden venir del entorno.
    # Si faltan las de la base de datos, conexion_bdd.py falla con un mensaje claro.
    warnings.warn(f"No se encontró el archivo .env en {ARCHIVO_ENV}. Copiá env.example a .env y completalo.")

load_dotenv(ARCHIVO_ENV)  # si el archivo no existe, no hace nada ni da error


def _ruta_desde_env(variable: str, por_defecto: str, crear: bool = False) -> Path:
    """
    Lee una variable nombre de carpeta del .env (o usa 'por_defecto'). Solo se crea en disco la carpeta si se pide con crear=True.
    """
    ruta_str = os.getenv(variable)
    # expanduser() traduce '~' a la carpeta del usuario actual
    ruta = Path((ruta_str or por_defecto).strip()).expanduser()
    ruta_absoluta = ruta if ruta.is_absolute() else RAIZ_PROYECTO / ruta

    if crear:
        ruta_absoluta.mkdir(parents=True, exist_ok=True)

    return ruta_absoluta


LOG_DIR_ABS = _ruta_desde_env("LOG_DIR", "logs", crear=True)
JSON_DIR_ABS = _ruta_desde_env("JSON_DIR", "json")
CONFIG_DIR_ABS = _ruta_desde_env("CONFIG_DIR", "config")
CHROMA_DIR_ABS = _ruta_desde_env("CHROMA_DIR", "chroma")

ALEMBIC_INI = RAIZ_PROYECTO / MARCADOR_RAIZ


