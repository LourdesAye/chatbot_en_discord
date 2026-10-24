from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Type

import yaml

from configuracion.gestor_yaml import Gestoryaml
from configuracion.claves_configuracion import ArchivoYAML, ClaveYAML
from database.models.clase_ruta import Ruta
from utils.config_paths import CONFIG_DIR_ABS
from utils.utilidades_logs import setup_logger

logger_cargador_yaml = setup_logger("logger_cargador_yaml", "cargador_yaml.txt")

# Interfaz o contrato del Repositorio
class Repositorio(ABC):
    """
    Obtiene datos externos requeridos para el correcto funcionamiento del sistema
    - lo nombres de los usuarios de Discord que son docentes
    - las frases comunes en preguntas
    - las frases habituales de cierre de conversaciones (tanto de docentes como de alumnos)
    - las frases que suelen estar incluidas en preguntas administrativas

    Uso de frozenset, que es particular de Python, para que sea un conjunti inmutable y evitar duplicados
    """

    @abstractmethod
    def obtener_docentes(self) -> frozenset[str]:
        """ Obtiene los nombres de usuario de Discord correspondientes a los docentes. """
        pass

    @abstractmethod
    def obtener_frases_administrativas(self) -> frozenset[str]:
        """ Obtiene las frases administrativas típicas en preguntas de alumnos """
        pass

    @abstractmethod
    def obtener_frases_cierre_alumnos(self) -> frozenset[str]:
        """ Obtiene las frases habituales de cierre de conversaciones por parte de alumnos"""
        pass

    @abstractmethod
    def obtener_frases_cierre_docentes(self) -> frozenset[str]:
        """ Obtiene las frases típicas utilizadas por los docentes para dar cierre a una conversación"""
        pass

    @abstractmethod
    def obtener_frases_habituales_en_preguntas(self) -> frozenset[str]:
        """ Obtiene las frases que suelen estar presentes en preguntas realizadas por alumnos """
        pass


class RepositorioYAML(Repositorio):
    """Repositorio de configuración basado en archivos YAML."""

    def __init__(
        self,
        gestor_yaml: Gestoryaml | None = None,
    ):
        self._gestor_yaml = gestor_yaml or Gestoryaml()

    def obtener_docentes(self) -> frozenset[str]:
        return self._gestor_yaml.obtener_contenido_del_yaml_segun_clave(
            ArchivoYAML.DOCENTES,
            ClaveYAML.DOCENTES,
        )

    def obtener_frases_administrativas(self) -> frozenset[str]:
        return self._gestor_yaml.obtener_contenido_del_yaml_segun_clave(
            ArchivoYAML.FRASES_ADMINISTRATIVAS,
            ClaveYAML.FRASES_ADMINISTRATIVAS,
        )

    def obtener_frases_cierre_alumnos(self) -> frozenset[str]:
        return self._gestor_yaml.obtener_contenido_del_yaml_segun_clave(
            ArchivoYAML.FRASES_CIERRE_ALUMNOS,
            ClaveYAML.FRASES_CIERRE_ALUMNOS,
        )

    def obtener_frases_cierre_docentes(self) -> frozenset[str]:
        return self._gestor_yaml.obtener_contenido_del_yaml_segun_clave(
            ArchivoYAML.FRASES_CIERRE_DOCENTE,
            ClaveYAML.FRASES_CIERRE_DOCENTE,
        )

    def obtener_frases_habituales_en_preguntas(
        self,
    ) -> frozenset[str]:
        return self._gestor_yaml.obtener_contenido_del_yaml_segun_clave(
            ArchivoYAML.FRASES_CLAVE_PREGUNTAS,
            ClaveYAML.FRASES_CLAVE_PREGUNTAS,
        )





