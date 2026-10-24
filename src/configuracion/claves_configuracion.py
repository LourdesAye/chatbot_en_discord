"""
- Centraliza los nombres de los archivos YAML y de las claves utilizadas para acceder a su contenido.
- Evita el hardcodeo y la duplicación de cadenas de caracteres ("strings mágicos") 
relacionadas con los archivos de configuración.
- Si en el futuro se agrega o modifica el nombre de un archivo YAML o de una de sus claves, 
el cambio debe realizarse únicamente en este archivo.
- El resto del proyecto utiliza estos valores centralizados en lugar de escribir directamente cadenas 
como "docentes.yaml" o "docentes".
- Las enumeraciones heredan de `str` y `Enum` para que sus miembros puedan utilizarse 
tanto como valores enumerados como cadenas de texto. Esto permite mantener los valores centralizados y, 
al mismo tiempo, utilizarlos en operaciones que requieren un `str`.
"""

from enum import Enum


class ArchivoYAML(str, Enum):
    """Nombres de los archivo ubicados en config/yaml/."""
    DOCENTES = "docentes.yaml"
    FRASES_ADMINISTRATIVAS = "frases_administrativas.yaml"
    FRASES_CIERRE_ALUMNOS = "frases_cierre_alumnos.yaml"
    FRASES_CIERRE_DOCENTE = "frases_cierre_docente.yaml"
    FRASES_CLAVE_PREGUNTAS = "frases_clave_preguntas.yaml"
    CONFIGURACION = "configuracion.yaml"

class ClaveYAML(str, Enum):
    """Claves utilizadas para acceder al contenido de los archivos YAML."""
    DOCENTES = "docentes"
    FRASES_ADMINISTRATIVAS = "frases_administrativas"
    FRASES_CIERRE_ALUMNOS = "frases_cierre_alumnos"
    FRASES_CIERRE_DOCENTE = "frases_cierre_docente"
    FRASES_CLAVE_PREGUNTAS = "frases_clave_preguntas"

class ClaveConfiguracion(str, Enum):
    """Claves anidadas dentro de configuracion.yaml (sección `umbrales`)."""
    UMBRALES = "umbrales"
    MAX_CARACTERES_RESPUESTA_CORTA = "max_caracteres_respuesta_corta"
    MAX_PALABRAS_PREGUNTA_SIN_CONTEXTO = "max_palabras_pregunta_sin_contexto"
    UMBRAL_SIMILITUD_FUZZY = "umbral_similitud_fuzzy"



