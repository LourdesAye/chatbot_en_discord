from psycopg2 import connect, errors, sql

from database.conector_bdd import ConectarBD
from utils.utilidades_logs import setup_logger
from validador import Validador

logger_db = setup_logger("carga_db", "log_persistencia_de_datos.txt")

class CrearBaseDeDatos:
    def __init__(self, config, validador:Validador):
        self.config = config
        self.conector_a_base_de_datos = ConectarBD(config)
        self.validador= validador

    def existe_base_de_datos(self, cursor,nombre_base_de_datos):
        """Verifica si la base de datos existe"""
        # Devuelve 1 si la base de datos existe, de lo contrario None
        cursor.execute(
            sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"),
            [nombre_base_de_datos],
        )
        return cursor.fetchone() is not None

    def crear_base_de_datos(self,cursor):
        logger_db.info(f"Creando base de datos {self.config['dbname']}...")
        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(self.config["dbname"])
            )
        )
        logger_db.info("✅ Base de datos creada exitosamente")
 

    def crear_base_de_datos_si_no_existe(self):
        """Crea la base de datos si no existe"""
        # Conexión temporal sin especificar la base de datos
        temp_conn = self.conector_a_base_de_datos.conectar_a_base_de_datos_no_existente()
        try:
            with temp_conn.cursor() as cur:
                # Verificar si la base de datos existe, sino crearla
                if not self.existe_base_de_datos(cur,self.config["dbname"]):
                    self.crear_base_de_datos(cur)
        except errors.DatabaseError as e:
            logger_db.error(f"❌ Error al crear la base de datos: {e}")
        finally:
            temp_conn.close()


class CargarDatosInicialesBaseDeDatos:
    def __init__(self, config,validador:Validador):
        self.config = config
        self.conector_a_base_de_datos = ConectarBD(config)
        self.validador=validador

    def hay_autores_en_base_de_datos(self,cursor):
        """Verifica si hay autores en la base de datos"""
        cursor.execute("SELECT COUNT(*) FROM autores")
        count = cursor.fetchone()[0]
        return count > 0

    def hay_docentes_para_insertar(self):
        """Verifica si hay docentes para insertar"""
        return bool(self.validador.obtener_docentes())

    def docentes_a_insertar(self):
        """Devuelve la lista de docentes para insertar"""
        return self.validador.obtener_docentes()

    def insertar_docente(self, cursor,docente):
        cursor.execute(
            "INSERT INTO autores (nombre_autor, es_docente) VALUES (%s, %s)",
            (docente, True),
        )

    # IMPORTANTE: Esta función debe llamarse después de crear la base de datos y establecer el esquema con Alembic
    def insertar_datos_inciales(self):
        """Inserta datos iniciales si las tablas están vacías"""
        conexion = self.conector_a_base_de_datos.conectar_a_base_de_datos_existente()
        try:
            with conexion.cursor() as cur:
                # Verificar si la tabla autores está vacía
                if not self.hay_autores_en_base_de_datos(cur) and self.hay_docentes_para_insertar():
                    logger_db.info("Insertando datos iniciales de autores...")
                    for docente in self.docentes_a_insertar():
                        self.insertar_docente(cur, docente)
                    conexion.commit()
                    logger_db.info("Datos iniciales de autores insertados")
        except errors.DatabaseError as e:
            logger_db.error(f"Error al insertar datos iniciales: {e}")
            conexion.rollback()
        finally:
            conexion.close()




