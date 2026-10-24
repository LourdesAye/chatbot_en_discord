import sys

from embeddings.modelo_embeddings import crear_modelo_embeddings

from configuracion.repository import RepositorioYAML
from database.analizador_preguntas_cerradas import AnalizadorPreguntasCerradas
from database.clase_cargar_bdd import GestorBD
from database.crear_bdd_e_inicializarla import (
    CargarDatosInicialesBaseDeDatos,
    CrearBaseDeDatos,
)
from embeddings.gestor_vectores import GestorBaseVectorial
from migraciones_automaticas.aplicar_migraciones_automaticas import (
    aplicar_migraciones_automaticas,
)
from processing.procesamiento_json import procesar_archivos_json
from utils.conexion_bdd import CONFIG
from utils.file_searcher import BuscadorArchivos
from utils.utilidades_logs import setup_logger
from validador import Validador


def main(): 
    logger_proc= setup_logger('carga_procesador','log_procesamiento_con_preguntas_cerradas.txt')

    # OBTENER DATOS NECESARIOS PARA EL SISTEMA
    repositorio = RepositorioYAML()
    validador = Validador(repositorio)

    # OBTENER RUTAS DE ARCHIVOS JSON
    buscador_archivos = BuscadorArchivos()
    rutas_json = buscador_archivos.obtener_rutas_json() 

    logger_proc.debug(f" 🗂️ Cantidad de archivos JSON encontrados: {len(rutas_json)}")
    if len(rutas_json) == 0:
        logger_proc.debug(" ❌ No se encontraron archivos JSON para procesar. Finalizando ejecución.")
        sys.exit(1)  # Salir del programa si no hay archivos JSON   

    # PROCESAMIENTO DE ARCHIVOS JSON
    logger_proc.debug("📎 Rutas de los JSON a procesar:")
    for num_ruta,ruta in enumerate(rutas_json,start=1):
        logger_proc.debug(f" 📌 Ruta {num_ruta} detectada: {ruta}")
    procesadores = procesar_archivos_json(rutas_json,validador) # función para procesar todos los archivos JSON   
    logger_proc.debug(f" 🔍 Cantidad de procesadores generados: {len(procesadores)}")
    logger_proc.debug(" 🗃️ Conectándose a la base de datos...") 

    # PERSISTENCIA EN BASE DE DATOS
    # Validar si existe BDD o crearla
    validador_existencia_bdd = CrearBaseDeDatos(CONFIG,validador)
    validador_existencia_bdd.crear_base_de_datos_si_no_existe()

    # Aplicar migraciones con Alembic
    aplicar_migraciones_automaticas()

    # Cargar datos iniciales en la base de datos si las tablas están vacías
    cargador_datos_iniciales = CargarDatosInicialesBaseDeDatos(CONFIG,validador)
    cargador_datos_iniciales.insertar_datos_inciales()

    bd = GestorBD(CONFIG,validador) 
    if bd.tiene_preguntas():
        logger_proc.debug( "⚠️ La base de datos ya contiene preguntas. Se cancela la carga para evitar duplicados.")
        bd.cerrar_conexion()
    else:
        cant_total_resp = 0 
        cant_total_preg =0 
        # Análisis y persistencia de preguntas cerradas por cada procesador
        for indice,proc in enumerate(procesadores,start=1): # por cada procesador 
            analizador = AnalizadorPreguntasCerradas(proc.preguntas_cerradas,validador)
            #se aplica analisis de preguntas sin contexto, preguntas administrativas y respuestas validadas
            cantidad_preguntas_json, cantidad_respuestas_json, preguntas_a_procesar = analizador.aplicar_analisis_preguntas(indice)
            # contador de preguntas y respuestas que va acumulando por cada json
            cant_total_preg = cant_total_preg + cantidad_preguntas_json
            cant_total_resp = cant_total_resp + cantidad_respuestas_json
            # persistencia de datos de la lista de preguntas cerradas con el analisis aplicado
            bd.persistir_preguntas(preguntas_a_procesar,indice)

        # Resumen final de la carga de datos
        logger_proc.debug(" ")
        logger_proc.debug(f" ✅ La cantidad total de preguntas generadas : {cant_total_preg}")
        logger_proc.debug(f" ✅ La cantidad total de respuestas generadas : {cant_total_resp}")
        bd.cerrar_conexion() # cerrar conexión con bdd
        logger_proc.debug(" ")
        logger_proc.debug(" 💾 Conexión cerrada y datos guardados.")

    # GESTIÓN DE LA BASE VECTORIAL DE EMBEDDINGS
    modelo = crear_modelo_embeddings()
    gestor_base_vectorial = GestorBaseVectorial(modelo)
    vectordb = gestor_base_vectorial.crear_si_no_existe()

    if vectordb:
        gestor_base_vectorial.buscar("¿Qué es Github?")
        gestor_base_vectorial.buscar("¿Cómo se usa el patrón state?")
        gestor_base_vectorial.buscar("¿qué es java?")

if __name__ == "__main__":
    main()


