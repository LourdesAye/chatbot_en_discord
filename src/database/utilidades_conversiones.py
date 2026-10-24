from dateutil.parser import isoparse


# convertir texto a datetime
def convertir_a_datetime(cadena_fecha):
      return isoparse(cadena_fecha) # convierte la cadena en un objeto datetime

# Función para calcular la diferencia de tiempo
def tiempo_transcurrido(pregunta_timestamp, mensaje_timestamp):
    return mensaje_timestamp - pregunta_timestamp