import os

from dotenv import load_dotenv

from utils.utilidades_logs import setup_logger

# Inicializar logger para esta parte del sistema
logger_db= setup_logger('carga_db','log_persistencia_de_datos.txt')

# Cargar variables desde .env
load_dotenv()

# Obtener configuración desde variables de entorno (.env)
CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# Validación con log
if not all(CONFIG.values()):
    logger_db.error("❌ Faltan variables de entorno para la conexión a la base de datos. Verificá el archivo .env.")
    raise ValueError("Faltan datos de conexión a la base de datos. Verificá el archivo .env")
else:
    logger_db.info("✅ Variables de entorno cargadas correctamente para la conexión a la base de datos.")
