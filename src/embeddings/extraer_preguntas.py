import psycopg2
from psycopg2.extras import DictCursor

from utils.conexion_bdd import CONFIG
from utils.utilidades_logs import setup_logger


def obtener_preguntas_y_metadatos():
    logger_preguntas = setup_logger("logger_embeddings", "logs_preguntas_para_embeddings.txt")
    preguntas, metadatos = [], []

    try:
        conn = psycopg2.connect(**CONFIG) # es la conexión a la base de datos PostgreSQL.
        # DictCursor hace que los resultados sean accesibles por nombre de columna (ej. fila["texto"]).
        cursor = conn.cursor(cursor_factory=DictCursor) # permite ejecutar consultas SQL y recorrer los resultados.
        cursor.execute("""
            SELECT DISTINCT p.id_pregunta, p.texto
            FROM preguntas p
            JOIN respuestas r ON r.pregunta_id = p.id_pregunta
            WHERE r.es_validada = true
              AND (p.sin_contexto IS NULL OR p.sin_contexto = false)
              AND (p.es_administrativa IS NULL OR p.es_administrativa = false)
        """) 
        resultados = cursor.fetchall() # Obtiene todos los resultados de la consulta

        if not resultados:
            logger_preguntas.warning("⚠️ No se encontraron preguntas válidas en la BDD")
            return [], []

        # Validación explícita de estructura de datos
        for fila in resultados:
            if not all(key in fila for key in ["id_pregunta", "texto"]):
                logger_preguntas.error("❌ Estructura de datos inesperada en fila")
                continue   
            preguntas.append(fila["texto"])
            metadatos.append({"id": fila["id_pregunta"]})

    except psycopg2.OperationalError as e:
        logger_preguntas.error(f"🚨 Error de conexión a la BDD: {e}")
        return [], []
    except psycopg2.Error as e:
        logger_preguntas.error(f"💾 Error en consulta SQL: {e}")
        return [], []
    except Exception as e:
        logger_preguntas.error(f"⚠️ Error inesperado: {e}")
        return [], []
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

    # Log de resumen final
    logger_preguntas.info(f"📊 Total de preguntas obtenidas de la base de datos relacional para generar embeddings : {len(preguntas)}")
    return preguntas, metadatos