import pandas as pd

from database.models.clase_ruta import Ruta
from processing.procesamiento_completo import ProcesadorBatch
from utils.filtros_de_mensajes import (
    EstrategiaFiltro,
    FiltroContenidoIrrelevanteVisual,
    FiltroContenidoVacio,
    FiltroSoloNumerosSignos,
    FiltroSoloSimbolos,
)
from utils.utilidades_logs import guardar_resultados_en_csvs, setup_logger
from validador import Validador

# agregando logger para seguimiento de la carga de datos
logger_proc= setup_logger('carga_procesador','log_procesamiento_con_preguntas_cerradas.txt')

# Función para procesar el archivo JSON y convertirlo a DataFrame
def cargar_json_como_dataframe(ruta_json : Ruta) -> pd.DataFrame : 
    datos = ruta_json.leer_json() # abre el JSON y lo pasa a un diccionario (par clave-valor)
    mensajes_crudos_df = pd.DataFrame(datos)  # Convierte el diccionario a DataFrame
    return mensajes_crudos_df # devuelve un dataframe (estructura de fila : datos o valor y columna: clave o nombre del atributo) con los datos del json


def aplicar_filtros_mensajes_json(
    mensajes_crudos_df: pd.DataFrame, filtros_mensajes: list[EstrategiaFiltro]
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    logger_proc.debug(f"\n✉️ Cantidad de mensajes en el json: {len(mensajes_crudos_df)}")
    # Limpiar espacios en blanco al inicio y al final de los contenidos de los mensajes
    mensajes_crudos_df["content"] = mensajes_crudos_df["content"].astype(str).str.strip()
    mensajes_limpios_df = mensajes_crudos_df.copy()
    mensajes_descartados = {}
    for estrategia in filtros_mensajes:
        nombre_filtro = estrategia.nombre()
        # Aplicación de la estrategia usando apply sobre la serie
        mask_descartados = mensajes_limpios_df["content"].apply(estrategia.aplicar)
        # Guardar los descartados en el diccionario
        mensajes_descartados[nombre_filtro] = mensajes_limpios_df[mask_descartados].copy()
        logger_proc.debug(f"🟡 Cantidad de mensajes filtrados por {nombre_filtro}: {len(mensajes_descartados[nombre_filtro])}")
        # Los que NO cumplen la condición de descarte (el negado ~mask)
        mensajes_limpios_df = mensajes_limpios_df[~mask_descartados]
    logger_proc.debug(f"🟢 Cantidad de mensajes luego de aplicar todos los filtros: {len(mensajes_limpios_df)}")
    return mensajes_limpios_df, mensajes_descartados

def _registrar_estadisticas_finales(logger, procesador, numero_json):
    """Función auxiliar encargada exclusivamente de volverse responsable 
    del reporte de métricas y estadísticas finales del procesamiento."""
    logger.debug("")
    logger.debug(f"\n✅ Procesamiento completado para el archivo JSON {numero_json}")
    logger.debug("📊 Resultados de procesamiento:")
    logger.debug("\n📊 Análisis de las listas de preguntas una vez finalizado el procesamiento:")
    logger.debug(f"     📊 {len(procesador.preguntas_abiertas)} preguntas abiertas")
    logger.debug(f"     📊 {len(procesador.preguntas_cerradas)} preguntas cerradas")
    logger.debug("\n📊 Análisis de los mensajes procesados:")
    logger.debug(f"     📊 {len(procesador.mensajes_sueltos)} mensajes sueltos")
    logger.debug(f"     📊 {procesador.cant_concatenaciones} mensajes concatenados")
    logger.debug(f"     📊 {procesador.cant_mens_cierre_alumnos} mensajes de cierre de alumnos")
    logger.debug(f"     📊 {procesador.contador_preguntas_nuevas} preguntas generadas")
    logger.debug(f"     📊 {procesador.contador_mensaje_respuesta} mensajes detectados como respuesta")
    
    total_analizados = (
        len(procesador.mensajes_sueltos) + 
        procesador.cant_concatenaciones + 
        procesador.cant_mens_cierre_alumnos + 
        procesador.contador_preguntas_nuevas + 
        procesador.contador_mensaje_respuesta
    )
    logger.debug(f"     ✅ {total_analizados} total de mensajes analizados")
    logger.debug(f"     📊 {procesador.cant_mens_cierre_docente} mensajes detectados como respuesta que también son de cierre de docentes")
    logger.debug(f"     📊 {procesador.cant_mens_cierre_alumnos + procesador.cant_mens_cierre_docente} mensajes totales de cierre")

    if len(procesador.mensajes_sueltos) >= 1:
        for indice, mensaje_suelto in enumerate(procesador.mensajes_sueltos, start=1):
            logger.debug("\n✉️ Listado de mensajes sueltos: ")
            logger.debug(f"✉️ El mensaje suelto {indice}: '{mensaje_suelto.contenido}'")
    logger.debug("")

def procesar_archivos_json(rutas_json: list[Ruta], validador: Validador) -> list[ProcesadorBatch]:
    procesadores = []

    for numero_json, ruta_json in enumerate(rutas_json, start=1):
        logger_proc.debug("")
        logger_proc.debug(f"📄 Procesando JSON {numero_json}")
        logger_proc.debug(f"📂 Ruta: {ruta_json}")

        mensajes_crudos_df = cargar_json_como_dataframe(ruta_json)
        prefijo_archivos_csv = f"chat_{numero_json}"
        
        filtros_mensajes: list[EstrategiaFiltro] = [
            FiltroContenidoVacio(),
            FiltroContenidoIrrelevanteVisual(),
            FiltroSoloNumerosSignos(),
            FiltroSoloSimbolos()
        ]

        mensajes_limpios_df, mensajes_descartados = aplicar_filtros_mensajes_json(mensajes_crudos_df, filtros_mensajes)
        guardar_resultados_en_csvs(mensajes_limpios_df, mensajes_descartados, prefijo_archivos_csv)

        nombre_log = f"log_json_{numero_json:02d}.txt"
        procesador = ProcesadorBatch(nombre_log, validador)
        # Ordenar y resetear índice
        mensajes_limpios_df = mensajes_limpios_df.sort_values(by='timestamp', ascending=True).reset_index(drop=True)
        procesador.procesar_dataframe(mensajes_limpios_df, str(ruta_json))
        procesadores.append(procesador)
        # Delegamos la responsabilidad del reporte de logs a la función auxiliar
        _registrar_estadisticas_finales(logger_proc, procesador, numero_json)

    return procesadores