import re
import unicodedata


class NormalizadorUsuario:
    """
    Normaliza nombres de usuario para realizar comparaciones.
    La normalización actual elimina espacios al comienzo y al final y convierte el texto a minúsculas.
    """

    @staticmethod
    def normalizar(usuario: str) -> str:
        """ Normaliza un nombre de usuario. """
        return usuario.strip().lower()

# ------------------- Funciones auxiliares ------------------------ #
def normalizar_espacios_internos(texto: str) -> str:
    """
    Normaliza espacios en un texto:
    - Reemplaza múltiples espacios internos por uno solo
    """
    if not isinstance(texto, str):
        return ""
    # re.sub reemplaza secuencias de espacios por uno solo
    texto = re.sub(r"\s+", " ", texto)
    return texto

def normalizar_espacios_externos(texto:str) -> str:
    """
    Normaliza espacios en un texto:
    - Quita espacios al inicio y al final
    """
    if not isinstance(texto, str):
        return ""
    # strip() elimina espacios al inicio y al final
    texto = texto.strip()
    return texto

def quitar_tildes(texto: str) -> str:
    """
    Elimina tildes y diacríticos de un texto.
    """
    if not isinstance(texto, str):
        return ""
    # Normaliza el texto a forma NFD (descompone caracteres en base + diacrítico)
    texto_normalizado = unicodedata.normalize("NFD", texto)
    # Elimina los diacríticos (categoría "Mn" en Unicode) y reconstruye el texto sin tildes
    texto_sin_tildes = "".join(
        c for c in texto_normalizado if unicodedata.category(c) != "Mn"
    )
    return texto_sin_tildes

def quitar_comillas(texto: str) -> str:
    """ 
    Quita comillas simples y dobles
    """
    texto = texto.replace("'", "").replace('"', "")
    return texto

def convertir_a_minusculas(texto: str) -> str:
    """
    Convierte un texto a minúsculas.
    """
    if not isinstance(texto, str):
        return ""
    return texto.lower()

def normalizar_saltos_de_linea(texto: str) -> str:
    """
    Normaliza saltos de línea en un texto:
    - Reemplaza múltiples saltos de línea por un solo espacio
    """
    if not isinstance(texto, str):
        return ""
    # Reemplaza múltiples saltos de línea por uno solo
    texto = re.sub(r"\s*\n\s*", " ", texto)
    return texto

def eliminar_caracteres_especiales(texto: str) -> str:
    """
    Elimina caracteres especiales, dejando solo letras (incluyendo acentuadas), números y espacios. Excluye guiones bajos.
    """
    if not isinstance(texto, str):
        return ""
    # Mantiene letras, números y espacios, pero NO guion bajo
    texto = re.sub(r"[^\w\s]", "", texto, flags=re.UNICODE)
    # Elimina guiones bajos que \w conserva
    texto = texto.replace("_", "")
    return texto









