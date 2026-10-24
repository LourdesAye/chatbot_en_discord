""" Se ocupa de leer el YAML """
from pathlib import Path
from typing import Any
from database.models.clase_ruta import Ruta

import yaml

from configuracion.claves_configuracion import ArchivoYAML, ClaveYAML
from utils.config_paths import CONFIG_DIR_ABS
from utils.utilidades_logs import setup_logger

logger = setup_logger( "logger_cargador_yaml", "cargador_yaml.txt",)

class Gestoryaml:
    """ Lee y valida archivos YAML de configuración. """

    def __init__(self, directorio_yaml: Path | None = None):
        self._directorio_yaml = ( directorio_yaml if directorio_yaml is not None else CONFIG_DIR_ABS / "yaml")
        self._cache: dict[str, dict[str, Any]] = {}

    def cargar_yaml_en_memoria(self, archivo: ArchivoYAML) -> dict[str, Any]:
        """ Carga un YAML y mantiene su contenido en caché. """

        nombre_archivo = archivo.value

        # el yaml ya se cargó en memoria en algún momento anterior
        if nombre_archivo in self._cache:
            return self._cache[nombre_archivo]

        ruta = Ruta(self._directorio_yaml / nombre_archivo)

        if not ruta.existe():
            raise FileNotFoundError(f"No existe el archivo YAML: {ruta}")

        try:
            with open(ruta.nombre_ruta,"r", encoding="utf-8") as archivo_yaml:
                contenido = yaml.safe_load(archivo_yaml)
        except yaml.YAMLError as exc:
            # ValueError: si el YAML es inválido
            logger.error( "Error de sintaxis YAML en %s", ruta,)
            raise ValueError(f"YAML inválido: {ruta}") from exc

        # ValueError: si el YAML está vacío
        if contenido is None:
            raise ValueError(f"El archivo {archivo.value} está vacío.")

        # ValueError: el contenido cargado desde el yaml no es un diccionario
        if not isinstance(contenido, dict):
            raise ValueError(f"El archivo {ruta.name} debe contener un diccionario YAML.")
            
        self._cache[nombre_archivo] = contenido
        return contenido

    def obtener_contenido_del_yaml_segun_clave( self, archivo: ArchivoYAML, clave: ClaveYAML,) -> frozenset[str]:
        """ Obtiene una lista de cadena de caracteres como conjunto inmutable. """

        contenido = self.cargar_yaml_en_memoria(archivo)

        # ValueError: el contenido del yaml no posee la sección o título buscado (datos esperados)
        if clave.value not in contenido:
            raise KeyError(f"No existe la clave '{clave.value}' " f"en {archivo.value}.")

        elementos_buscados = contenido[clave.value]

        # ValueError: existe el título o sección en en yaml, pero no tiene el formato esperado (lista)
        if not isinstance(elementos_buscados, list):
            raise ValueError(f"'{clave.value}' en {archivo.value} " "debe contener una lista.")

        # ValueError : Todos los elementos de la lista de datos deben ser str (cadena de caracteres)
        if not all(isinstance(elemento, str) for elemento in elementos_buscados):
            raise ValueError(f"Todos los elementos de '{clave.value}' " "deben ser strings.")

        elementos = frozenset(elementos_buscados)
        logger.info("%s -> '%s': %d elementos (%d únicos)",
                    archivo.value, clave.value, len(elementos_buscados), len(elementos))
        return elementos
