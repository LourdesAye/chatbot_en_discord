from datetime import timedelta
from typing import TYPE_CHECKING

from database.models.clase_mensajes import Mensaje
from database.models.clase_preguntas import Pregunta
from database.utilidades_conversiones import convertir_a_datetime, tiempo_transcurrido
from processing.procesamiento_completo import ProcesadorBatch
from utils.utilidades_logs import setup_logger
from validador import Validador

if TYPE_CHECKING:
    from database.clase_cargar_bdd import GestorBD
    from embeddings.gestor_vectores import GestorBaseVectorial

logger_tr = setup_logger('procesamiento_tiempo_real', 'log_procesamiento_tiempo_real.txt')

# Una pregunta que nadie respondió con un docente en este tiempo se descarta,
# para que no siga absorbiendo mensajes nuevos como si fueran respuestas.
TIEMPO_DESCARTE_SIN_RESPUESTA_HORAS = 24
# Un mensaje sin preguntas abiertas solo se asocia a las últimas preguntas cerradas
# si llega dentro de esta ventana desde su última actividad (si no, queda como mensaje suelto).
VENTANA_RESPUESTA_TARDIA_MINUTOS = 60
# Solo se necesitan las últimas preguntas cerradas (para asociarles respuestas tardías).
MAX_PREGUNTAS_CERRADAS_EN_MEMORIA = 10


class ProcesadorTiempoReal(ProcesadorBatch):
    """Procesa mensajes de Discord a medida que llegan.

    Reutiliza las mismas reglas que el procesamiento por lotes (las preguntas abiertas se
    mantienen en memoria) y agrega, al cerrarse una pregunta:
      1. su análisis (sin contexto / administrativa),
      2. su persistencia en PostgreSQL,
      3. su indexación en la base vectorial, si es apta para el chatbot.
    Las respuestas que llegan después del cierre se agregan a la base de datos.
    Las preguntas abiertas viven en memoria: si el bot se reinicia, se pierden.
    """

    def __init__(
        self,
        nombre_log,
        validador: Validador,
        gestor_bd: "GestorBD",
        gestor_vectorial: "GestorBaseVectorial",
        estrategias=None,
    ):
        super().__init__(nombre_log, validador, estrategias)
        self.gestor_bd = gestor_bd
        self.gestor_vectorial = gestor_vectorial
        self.contador_preguntas_descartadas = 0
        self.contador_preguntas_indexadas = 0
        self._momento_actual = None  # fecha del mensaje que se está procesando

    def procesar_mensaje(self, mensaje: Mensaje):
        self._momento_actual = convertir_a_datetime(mensaje.timestamp)
        self._descartar_preguntas_vencidas(mensaje)
        super().procesar_mensaje(mensaje)

    def obtener_preguntas_cerradas_recientes(self, limite=2):
        recientes = super().obtener_preguntas_cerradas_recientes(limite)
        if self._momento_actual is None:
            return recientes
        ventana = timedelta(minutes=VENTANA_RESPUESTA_TARDIA_MINUTOS)
        return [p for p in recientes if self._momento_actual - convertir_a_datetime(self._ultima_actividad(p)) <= ventana]

    @staticmethod
    def _ultima_actividad(pregunta: Pregunta):
        return pregunta.respuestas[-1].timestamp if pregunta.respuestas else pregunta.timestamp

    def _descartar_preguntas_vencidas(self, mensaje: Mensaje):
        ahora = convertir_a_datetime(mensaje.timestamp)
        limite = timedelta(hours=TIEMPO_DESCARTE_SIN_RESPUESTA_HORAS)
        for pregunta in list(self._preguntas_abiertas):
            if pregunta.tiene_respuesta_validada():
                continue
            if tiempo_transcurrido(convertir_a_datetime(pregunta.timestamp), ahora) > limite:
                self._preguntas_abiertas.remove(pregunta)
                self.contador_preguntas_descartadas += 1
                logger_tr.debug(f"🗑️ Pregunta descartada por falta de respuesta docente: {pregunta.contenido}")

    def registrar_cierre(self, pregunta: Pregunta, motivo: str):
        super().registrar_cierre(pregunta, motivo)  # la mueve de abiertas a cerradas
        pregunta.marcar_sin_contexto_si_corta()
        pregunta.marcar_administrativa(self.validador.obtener_frases_administrativas())
        try:
            pregunta.id_pregunta_bd = self.gestor_bd.persistir_pregunta_tiempo_real(pregunta)
        except Exception:
            logger_tr.exception(f"❌ No se pudo persistir la pregunta: {pregunta.contenido}")
        else:
            self._indexar_si_corresponde(pregunta)
        excedente = len(self.preguntas_cerradas) - MAX_PREGUNTAS_CERRADAS_EN_MEMORIA
        if excedente > 0:
            del self.preguntas_cerradas[:excedente]

    def _indexar_si_corresponde(self, pregunta: Pregunta):
        # Mismo criterio que embeddings.extraer_preguntas: respuesta validada, con contexto y no administrativa
        if pregunta.sin_contexto or pregunta.es_administrativa or not pregunta.tiene_respuesta_validada():
            logger_tr.debug(f"⏭️ La pregunta no se indexa (sin contexto/administrativa/sin validar): {pregunta.contenido}")
            return
        try:
            self.gestor_vectorial.agregar_pregunta(pregunta.id_pregunta_bd, pregunta.contenido)
            self.contador_preguntas_indexadas += 1
        except Exception:
            logger_tr.exception(f"❌ No se pudo indexar la pregunta {pregunta.id_pregunta_bd}")

    def asociar_respuesta_a_multiples(self, preguntas_cerradas: list[Pregunta], mensaje: Mensaje):
        super().asociar_respuesta_a_multiples(preguntas_cerradas, mensaje)
        for pregunta in preguntas_cerradas:
            if pregunta.id_pregunta_bd is None:
                logger_tr.warning("⚠️ Pregunta cerrada sin id en la base: la respuesta tardía no se persiste")
                continue
            try:
                self.gestor_bd.persistir_respuesta_tardia(pregunta.id_pregunta_bd, pregunta.respuestas[-1])
            except Exception:
                logger_tr.exception(f"❌ No se pudo persistir la respuesta tardía de la pregunta {pregunta.id_pregunta_bd}")

    def registrar_mensaje_suelto(self, mensaje: Mensaje):
        # En tiempo real no se acumulan: solo se deja registro en el log
        logger_tr.debug(f"🔴 MENSAJE SUELTO: '{mensaje.contenido}' de {mensaje.autor}")
