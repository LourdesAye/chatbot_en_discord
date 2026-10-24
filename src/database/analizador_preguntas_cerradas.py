from database.models.clase_preguntas import Pregunta
from utils.utilidades_logs import setup_logger
from validador import Validador

logger_proc= setup_logger('carga_procesador','log_procesamiento_con_preguntas_cerradas.txt')

class AnalizadorPreguntasCerradas:
    def __init__(self, preguntas : list[Pregunta], validador : Validador):
        self.cant_preg_sin_contexto =0 
        self.cant_preg_cerradas = 0
        self.cant_respuestas = 0
        self.preguntas=preguntas
        self.validador = validador

    def marcar_preguntas_sin_contexto(self):
        for pregunta in self.preguntas:
            pregunta.marcar_sin_contexto_si_corta()
        return self.preguntas

    def agregar_es_administrativa (self,preguntas_a_marcar: list[Pregunta]):
        frases_admin = self.validador.obtener_frases_administrativas()
        for pregunta in preguntas_a_marcar:
            pregunta.marcar_administrativa(frases_admin)
        return preguntas_a_marcar

    def marcar_respuestas_cortas(self,preguntas_a_marcar: list[Pregunta]):
        for pregunta in preguntas_a_marcar:
            for respuesta in pregunta.respuestas:
                respuesta.marcar_como_corta()
        return preguntas_a_marcar
    
    def aplicar_analisis_preguntas(self, num_procesador):
            logger_proc.debug(f"\n🔢 Analizando el json número : {num_procesador} ... ")
            logger_proc.debug(f"\n✅ Preguntas cerradas: {len(self.preguntas)}\n")

            # Aplicamos los filtros secuencialmente
            self.marcar_preguntas_sin_contexto()
            self.agregar_es_administrativa(self.preguntas)
            self.marcar_respuestas_cortas(self.preguntas)

            # Calculamos métricas en una sola pasada limpia
            self.cant_preg_sin_contexto = sum(1 for p in self.preguntas if p.sin_contexto)
            self.cant_respuestas = sum(len(p.respuestas) for p in self.preguntas)

            logger_proc.debug(f"\n✅ Preguntas sin contexto: {self.cant_preg_sin_contexto}\n")
            logger_proc.debug(f"\n✅ Cantidad de Respuestas: {self.cant_respuestas}")

            return len(self.preguntas), self.cant_respuestas, self.preguntas