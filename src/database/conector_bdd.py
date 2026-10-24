from psycopg2 import connect, errors, sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from utils.utilidades_logs import setup_logger

logger_db = setup_logger("carga_db", "log_persistencia_de_datos.txt")

class ConectarBD:
    def __init__(self, config):
        self.config = config

    def conectar_a_base_de_datos_existente(self):
        """Establece conexión con la base de datos"""
        try:
            conn = connect(
                dbname=self.config["dbname"],
                user=self.config["user"],
                password=self.config["password"],
                host=self.config["host"],
                port=self.config["port"],
            )
            logger_db.info("Conexión a la base de datos establecida")
            return conn
        except errors.OperationalError as e:
            logger_db.error(f"Error al conectar a la base de datos: {e}")
            raise

    def conectar_a_base_de_datos_no_existente(self):
        """Establece conexión con la base de datos sin especificar el nombre de la base de datos"""
        # Conexión temporal sin especificar la base de datos
        temp_conn = connect(
            user=self.config["user"],
            password=self.config["password"],
            host=self.config["host"],
            port=self.config["port"],
        )
        # necesario para CREATE DATABASE
        temp_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        logger_db.info("Conexión temporal establecida para crear la base de datos")
        return temp_conn