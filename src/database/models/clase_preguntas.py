from database.models.clase_mensajes import Mensaje
from database.models.clase_respuestas import Respuesta
from database.models.utilidades_modelo_dominio import MAX_PALABRAS_PREGUNTA_SIN_CONTEXTO
from database.utilidades_conversiones import convertir_a_datetime, tiempo_transcurrido


class Pregunta:
    def __init__(self, mensaje: Mensaje):
        self.id_pregunta = mensaje.id_mensaje_discord
        self.id_pregunta_bd: int | None = None  # se completa al persistirla (tiempo real)
        self.autor = mensaje.autor
        self.contenido = mensaje.contenido
        self.timestamp = mensaje.timestamp
        self.attachments = mensaje.attachments
        self.origen = mensaje.origen
        self.respuestas :list[Respuesta] = []
        self.cerrada = False
        self.sin_contexto = False
        self.es_administrativa = False
        self.validador = mensaje.validador

    def agregar_respuesta(self, mensaje: Mensaje):            
        respuesta = Respuesta(mensaje)
        if self.validador.es_docente(mensaje.autor):
            respuesta.validar()
        respuesta.marcar_como_corta()
        self.respuestas.append(respuesta)

    def cerrar(self):
        self.cerrada = True

    def tiene_respuesta_validada(self):
        return any(r.es_validada for r in self.respuestas)

    def marcar_sin_contexto_si_corta(self):
        if len(self.contenido.split()) <= MAX_PALABRAS_PREGUNTA_SIN_CONTEXTO:
            self.sin_contexto = True

    def marcar_administrativa(self, frases_admin):
        for frase in frases_admin:
            # Se utiliza strip() para eliminar espacios en blanco al inicio y al final de la frase, y lower() para hacer la comparación sin importar mayúsculas o minúsculas.
            if frase.strip().lower() in self.contenido.lower():
                self.es_administrativa = True
                break

    def es_extensible_con(self, mensaje,max_seg):
        if self.respuestas:
            return False
        diferencia_de_tiempo = tiempo_transcurrido(
            convertir_a_datetime(self.timestamp), 
            convertir_a_datetime(mensaje.timestamp))
        # no usar .seconds() porque solo considera segundos descartando días, horas, minutos
        # total_seconds() si considera total de segundos tomando días, minutos, etcétera
        return 0 <=diferencia_de_tiempo.total_seconds() < max_seg
    
    def tiene_mismo_autor(self,mensaje: Mensaje):
        return self.autor== mensaje.autor
    
    def concatenar_contenido(self, nuevo_texto):
        self.contenido = f"{self.contenido.rstrip()} {nuevo_texto.lstrip()}"
        # rstrip(): Elimina los espacios en blanco (incluyendo saltos de línea) que puedan estar al final
        # lstrip(): Elimina los espacios en blanco al inicio
