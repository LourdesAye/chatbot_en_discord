# --- Utilidades ---

def primeras_cinco_palabras(texto):
    return ' '.join(texto.split()[:5])

def contar_palabras(texto):
    return len(texto.split())

# --- Reglas y configuración ---

MAX_CARACTERES_RESP_CORTA = 14
MAX_PALABRAS_PREGUNTA_SIN_CONTEXTO = 6