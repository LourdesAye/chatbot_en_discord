"""
Lógica de búsqueda de archivos.
"""
import os
from pathlib import Path

from database.models.clase_ruta import Ruta
from utils.config_paths import JSON_DIR_ABS


class BuscadorArchivos:
    """Clase responsable de localizar y filtrar los archivos JSON en la estructura del proyecto."""

    def obtener_rutas_json(self, directorio_base: Path | None = None) -> list[Ruta]:
        """Obtiene las rutas validadas de todos los archivos JSON encontrados."""
        directorio_base = directorio_base or JSON_DIR_ABS
        
        if not directorio_base.exists():
            raise FileNotFoundError(f"El directorio no existe: {directorio_base}")

        resultados: list[Ruta] = []
        patron_de_busqueda = os.getenv("FILE_NAME", "chat.json")
        profundidad_maxima = int(os.getenv("MAX_DEPTH", 999))

        # rglob ya busca recursivamente de forma nativa en pathlib
        for ruta_archivo in directorio_base.rglob(patron_de_busqueda):
            if not ruta_archivo.is_file():
                continue

            # Cálculo limpio usando propiedades nativas de pathlib
            ruta_relativa = ruta_archivo.relative_to(directorio_base)
            profundidad = len(ruta_relativa.parents)

            if profundidad <= profundidad_maxima:
                ruta_obj = Ruta(ruta_archivo)
                if ruta_obj.existe():
                    resultados.append(ruta_obj)

        return resultados