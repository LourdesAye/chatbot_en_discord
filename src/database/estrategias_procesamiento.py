from abc import ABC, abstractmethod

from database.models.clase_mensajes import Mensaje
from utils.utilidades_logs import setup_logger

logger_msj = setup_logger('procesamiento_de_mensajes', 'logs_procesar_mensajes.txt')
MAX_DELTA_SEGUNDOS_MSJ = 360

class ProcesamientoStrategy(ABC):
    @abstractmethod
    def procesar(self, procesador, mensaje: Mensaje):
        pass

class ProcesamientoDocenteStrategy(ProcesamientoStrategy):
    def procesar(self, procesador, mensaje: Mensaje):
        # El procesador encapsula si busca en memoria (batch) o en DB (tiempo real)
        # Devuelve lista real interna del procesador 
        preguntas_abiertas = procesador.obtener_preguntas_abiertas()
        
        if preguntas_abiertas:

            # Se cuenta el mensaje UNA sola vez, aunque después se lo asocie a varias preguntas abiertas
            procesador.contar_mensaje_como_respuesta()
            # Se itera sobre una copia: cerrar_pregunta() remueve elementos de la lista real de preguntas abiertas, 
            # y modificar una lista mientras se la recorre hace que se salteen elementos.
            for pregunta in list(preguntas_abiertas):
                procesador.agregar_respuesta_a_pregunta(pregunta, mensaje)
                logger_msj.debug(f"✅️ Se ha agregado respuesta docente: {mensaje.contenido}")
                
                if mensaje.es_cierre_docente():
                    procesador.cerrar_pregunta(pregunta, mensaje, motivo='docente')
        else:
            # Si no hay abiertas, delegar la búsqueda de cerradas al procesador
            preguntas_cerradas_recientes = procesador.obtener_preguntas_cerradas_recientes(limite=2)
            if preguntas_cerradas_recientes:
                procesador.asociar_respuesta_a_multiples(preguntas_cerradas_recientes, mensaje)
            else:
                procesador.registrar_mensaje_suelto(mensaje)

class ProcesamientoAlumnoStrategy(ProcesamientoStrategy):
    def procesar(self, procesador, mensaje: Mensaje):
        preguntas_abiertas = procesador.obtener_preguntas_abiertas()
        if preguntas_abiertas:
            preguntas_activas_autor = procesador.obtener_preguntas_abiertas_por_autor(mensaje.autor)
            if preguntas_activas_autor:
                for pregunta in preguntas_activas_autor:
                    if pregunta.es_extensible_con(mensaje, MAX_DELTA_SEGUNDOS_MSJ):
                        procesador.concatenar_a_pregunta(pregunta, mensaje)
                        logger_msj.debug(f"📌 Se concatenó la pregunta: {pregunta.contenido} con el mensaje: {mensaje.contenido}")
                    elif mensaje.es_cierre_alumno() and pregunta.tiene_respuesta_validada():
                        procesador.cerrar_pregunta(pregunta, mensaje, motivo='alumno')
                        logger_msj.debug(f"❌ Se cerró la pregunta por cierre de alumno: {pregunta.contenido}")
                    else:
                        procesador.agregar_respuesta_a_pregunta(pregunta, mensaje)
                        procesador.contar_mensaje_como_respuesta()
                        logger_msj.debug(f"✅️ Se ha agregado respuesta alumno: {mensaje.contenido}")
            else:
                if mensaje.es_pregunta():
                    procesador.crear_nueva_pregunta(mensaje)
                else:
                    # un solo mensaje que será respuesta de varias preguntas abiertas
                    procesador.contar_mensaje_como_respuesta() 
                    # Se itera sobre una copia porque modificar una lista mientras se la recorre 
                    # hace que se salteen elementos.
                    for pregunta in list(preguntas_abiertas):
                        procesador.agregar_respuesta_a_pregunta(pregunta, mensaje)
                        logger_msj.debug(f"✅️ Se ha agregado respuesta alumno: {mensaje.contenido}")
        else:
            if mensaje.es_pregunta():
                procesador.crear_nueva_pregunta(mensaje)
            else: 
                preguntas_cerradas_recientes = procesador.obtener_preguntas_cerradas_recientes(limite=2)
                if preguntas_cerradas_recientes:
                    procesador.asociar_respuesta_a_multiples(preguntas_cerradas_recientes, mensaje)
                else:
                    procesador.registrar_mensaje_suelto(mensaje)
