from database.models.clase_mensajes import Mensaje
from database.models.utilidades_modelo_dominio import MAX_CARACTERES_RESP_CORTA


class Respuesta:
    def __init__(self, mensaje:Mensaje):
        self.id_respuesta = mensaje.id_mensaje_discord
        self.autor = mensaje.autor
        self.contenido = mensaje.contenido
        self.timestamp = mensaje.timestamp
        self.attachments= mensaje.attachments
        self.origen = mensaje.origen
        self.es_validada = False
        self.es_corta= False
    

    def validar(self):
        self.es_validada=True
    
    def marcar_como_corta(self):
        if len(self.contenido) <= MAX_CARACTERES_RESP_CORTA:
            self.es_corta = True


        