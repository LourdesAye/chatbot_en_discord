from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)

from utils.utilidades_logs import setup_logger

logger_migraciones_alembic = setup_logger('migraciones_alembic', 'log_migraciones_alembic_automaticas.txt')

def aplicar_migraciones_automaticas():
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger_migraciones_alembic.debug(" ✅ Migraciones aplicadas con éxito.")

    except CommandError as e:
        logger_migraciones_alembic.error(f" ❌ Error estructural de Alembic: {e}")
        raise

    except OperationalError as e:
        logger_migraciones_alembic.error(f" ❌ No se pudo conectar a la base: {e}")
        raise

    except IntegrityError as e:
        logger_migraciones_alembic.error(f" ❌ Error de integridad en la base: {e}")
        raise

    except ProgrammingError as e:
        logger_migraciones_alembic.error(f" ❌Error de sintaxis SQL en la migration: {e}")
        raise

    except SQLAlchemyError as e:
        logger_migraciones_alembic.error(f" ❌ Error general de SQLAlchemy/PostgreSQL: {e}")
        raise

    except RuntimeError as e:
        logger_migraciones_alembic.error(f" ❌ Error de configuración: {e}")
        raise

    except Exception as e:
        logger_migraciones_alembic.error(f" ❌ Error inesperado: {e}")
        raise 
