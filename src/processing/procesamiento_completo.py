from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List

import pandas as pd

from database.estrategias_procesamiento import (
    ProcesamientoAlumnoStrategy,
    ProcesamientoDocenteStrategy,
    ProcesamientoStrategy,
)
from database.models.clase_mensajes import Mensaje
from database.models.clase_preguntas import Pregunta
from database.utilidades_conversiones import convertir_a_datetime, tiempo_transcurrido
from processing.estrategias_cierre_mensajes.estrategias_cierre_mensajes import (
    EstrategiaCierre,
    EstrategiaCierreBatch,
)
from utils.utilidades_logs import guardar_pregunta_y_respuestas_en_log, setup_logger
from validador import Validador

logger_msj = setup_logger('procesamiento_de_mensajes', 'logs_procesar_mensajes.txt')

# Constantes globales del sistema de procesamiento 
MAX_RESPUESTAS = 7
TIEMPO_CIERRE_HORAS = 8

class ProcesadorBase(ABC): # importante heredar de ABC
    def __init__(self, nombre_log,validador: Validador,  estrategias=None):
        """Constructor común para ambos procesadores (batch y tiempo real)."""
        self.nombre_log :str = nombre_log
        self._preguntas_abiertas : list[Pregunta] = []
        self.preguntas_cerradas : list[Pregunta] = []
        self.estrategias : dict[str, ProcesamientoStrategy] = estrategias or {
            'docente': ProcesamientoDocenteStrategy(),
            'alumno': ProcesamientoAlumnoStrategy()
        }
        self.estrategia_cierre : EstrategiaCierre | None= None # se define en las subclases
        self.validador = validador

    @property 
    @abstractmethod 
    def preguntas_abiertas(self):
        pass

    @abstractmethod 
    def obtener_preguntas_abiertas_por_autor(self, autor):
        pass
    
    def cerrar_pregunta(self, pregunta: Pregunta, mensaje: Mensaje, motivo=None):
        self.estrategia_cierre.cerrar(pregunta, mensaje, motivo) # FALTA CERRAR PREGUNTA PARA REAL TIME
    
    def cerrar_por_reglas(self, mensaje: Mensaje):
        ahora = convertir_a_datetime(mensaje.timestamp)
        for pregunta in list(self._preguntas_abiertas): # en lo que es tiempo real la lista debe ser el resultado de una consulta a la base de datos de preguntas abiertas
            tiempo = tiempo_transcurrido(convertir_a_datetime(pregunta.timestamp), ahora)
            if pregunta.tiene_respuesta_validada(): # en tiempo real se debe tomar la pregunta con su id, buscarlo en la base de datos en la tabla respuestas, de las respuestas obtengo un id de usuario y por cada id de susuario hay que ir a al tabla autor para saber si es o no docente y por lo tanto si esta validada
                if tiempo > timedelta(hours=TIEMPO_CIERRE_HORAS):
                    self.cerrar_pregunta(pregunta, mensaje, motivo='tiempo')
                elif len(pregunta.respuestas) >= MAX_RESPUESTAS:
                    self.cerrar_pregunta(pregunta, mensaje, motivo='cantidad')


    def procesar_mensaje(self, mensaje: Mensaje):
        self.cerrar_por_reglas(mensaje)
        tipo= 'docente' if mensaje.es_autor_docente() else 'alumno'
        self.estrategias[tipo].procesar(self, mensaje)

class ProcesadorBatch(ProcesadorBase):
    # Extiende ProcesadorBase con atributos adicionales
    def __init__(self, nombre_log, validador: Validador, estrategias=None, ):
        # Llama al constructor de la clase base
        super().__init__(nombre_log,validador, estrategias) 
        # nuevos atributos específicos para batch
        self.mensajes_sueltos = []
        self.contador_mensajes = 0
        self.contador_preguntas_nuevas = 0
        self.contador_preguntas_cerradas = 0
        self.cant_concatenaciones = 0
        self.contador_mensaje_respuesta = 0
        self.cant_mens_cierre_alumnos = 0
        self.cant_mens_cierre_docente = 0
        self.estrategia_cierre = EstrategiaCierreBatch(self)  

    @property 
    def preguntas_abiertas(self):
        return self._preguntas_abiertas

    def registrar_cierre(self, pregunta: Pregunta, motivo: str):
        self.preguntas_abiertas.remove(pregunta)
        self.preguntas_cerradas.append(pregunta)
        self.contador_preguntas_cerradas += 1
        if motivo == 'alumno':
            self.cant_mens_cierre_alumnos += 1
        elif motivo == 'docente':
            self.cant_mens_cierre_docente += 1
        logger_msj.debug(f"🟢 PREGUNTA CERRADA por {motivo}")

    def procesar_dataframe(self, mensajes_limpios_df : pd.DataFrame, ruta_json : str):
        logger_msj.debug(" 🔵 Iniciando procesamiento del DataFrame...")
        for _, fila_df in mensajes_limpios_df.iterrows(): # obtener índice específico que no siempre es número y fila completa del Dataframe
            mensaje = Mensaje.convertir_fila_a_mensaje(fila_df, ruta_json,self.validador)
            self.contador_mensajes += 1
            logger_msj.debug(f" ... PROCESANDO MENSAJE {self.contador_mensajes}: '{mensaje.contenido}' ")
            self.procesar_mensaje(mensaje)
        logger_msj.debug("✅ PROCESAMIENTO FINALIZADO.")
        for numero_pregunta,pregunta in enumerate(self.preguntas_cerradas,start=1):
            guardar_pregunta_y_respuestas_en_log(pregunta, numero_pregunta,self.nombre_log)
        logger_msj.debug(f"Total mensajes: {self.contador_mensajes}, Preguntas nuevas: {self.contador_preguntas_nuevas}, Cerradas: {self.contador_preguntas_cerradas}")

    def registrar_mensaje_suelto(self, mensaje: Mensaje):
        self.mensajes_sueltos.append(mensaje)
        autor_tipo = "DOCENTE" if mensaje.es_autor_docente() else "ALUMNO"
        logger_msj.debug(f" 🔴 MENSAJE SUELTO: '{mensaje.contenido}' de {autor_tipo} : {mensaje.autor} ")

    def asociar_respuesta_a_preguntas_cerradas(self, mensaje):
        self.contador_mensaje_respuesta += 1
        cantidad = len(self.preguntas_cerradas)
        preguntas_a_asociar = (
            self.preguntas_cerradas[-1:]
            if cantidad == 1
            else self.preguntas_cerradas[-2:]
        )
        for pregunta in preguntas_a_asociar:
            pregunta.agregar_respuesta(mensaje)
            logger_msj.debug(f" 🔶 RESPUESTA QUE LLEGA SIN PREGUNTAS ABIERTAS: '{mensaje.contenido}'")
            logger_msj.debug(f" 🔶 SE ASOCIA A LA PREGUNTA CERRADA: '{pregunta.contenido}'")

    def obtener_preguntas_abiertas(self):
        return self._preguntas_abiertas

    def obtener_preguntas_cerradas_recientes(self, limite=2):
        cantidad = len(self.preguntas_cerradas)
        if cantidad == 0:
            return []
        return self.preguntas_cerradas[-limite:]

    def agregar_respuesta_a_pregunta(self, pregunta : Pregunta, mensaje : Mensaje):
        pregunta.agregar_respuesta(mensaje)

    def contar_mensaje_como_respuesta(self):
        self.contador_mensaje_respuesta += 1

    def concatenar_a_pregunta(self, pregunta : Pregunta, mensaje : Mensaje):
        pregunta.concatenar_contenido(mensaje.contenido)
        self.cant_concatenaciones += 1
        logger_msj.debug(f"📌 Se concatenó la pregunta: \n{pregunta.contenido}\n con el mensaje: {mensaje.contenido}")

    def crear_nueva_pregunta(self, mensaje : Mensaje):
        nueva = Pregunta(mensaje)
        self._preguntas_abiertas.append(nueva)
        self.contador_preguntas_nuevas += 1
        logger_msj.debug(f"🟡 NUEVA PREGUNTA: {nueva.contenido}")

    def asociar_respuesta_a_multiples(self, preguntas_cerradas :List[Pregunta], mensaje : Mensaje):
        self.contador_mensaje_respuesta += 1
        for pregunta in preguntas_cerradas:
            pregunta.agregar_respuesta(mensaje)
            logger_msj.debug(f"🔶 RESPUESTA A PREGUNTA CERRADA: '{pregunta.contenido}'")

    def obtener_preguntas_abiertas_por_autor(self, autor)-> List[Pregunta] : 
        lista_preguntas = [pregunta for pregunta in self.preguntas_abiertas if pregunta.autor == autor]
        return lista_preguntas



    