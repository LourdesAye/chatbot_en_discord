"""
Configuración del entorno del proyecto y de los directorios.
Utiliza pathlib para la gestión robusta de rutas y dotenv para el entorno.
"""
import os
from pathlib import Path

from dotenv import load_dotenv


def buscar_archivo_en_padres(nombre_archivo: str, directorio_inicio: Path | None = None) -> Path:
    """Busca un archivo recorriendo los directorios padres hacia arriba."""
    if directorio_inicio is None:
        try:
            directorio_inicio = Path(__file__).resolve().parent
        except NameError:
            directorio_inicio = Path.cwd()

    directorio_actual = directorio_inicio
    while True:
        ruta_candidata = directorio_actual / nombre_archivo
        if ruta_candidata.exists() and ruta_candidata.is_file():
            return ruta_candidata
        if directorio_actual.parent == directorio_actual:
            raise FileNotFoundError(
                f"❌ No se pudo encontrar {nombre_archivo} en ningún directorio padre de {directorio_inicio}"
            )
        directorio_actual = directorio_actual.parent


def configurar_entorno(nombre_archivo: str = ".env") -> Path:
    """Inicializa el entorno cargando las variables del .env y retorna la ruta raíz."""
    ruta_archivo_env = buscar_archivo_en_padres(nombre_archivo)
    load_dotenv(dotenv_path=ruta_archivo_env)
    return ruta_archivo_env.parent


CARPETA_PROYECTO = configurar_entorno()

LOG_DIR = os.getenv("LOG_DIR", "logs")
JSON_DIR = os.getenv("JSON_DIR", "json")
CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma")
DOCS_DIR = os.getenv("DOCS_DIR", "docs")
CONFIG_DIR = os.getenv("CONFIG_DIR", "config")

LOG_DIR_ABS = CARPETA_PROYECTO / LOG_DIR
JSON_DIR_ABS = CARPETA_PROYECTO / JSON_DIR
CHROMA_DIR_ABS = CARPETA_PROYECTO / CHROMA_DIR
CONFIG_DIR_ABS = CARPETA_PROYECTO / CONFIG_DIR


