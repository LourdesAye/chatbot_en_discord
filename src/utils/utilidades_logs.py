import logging

import os

from datetime import datetime

import pandas as pd

from utils.config_paths import LOG_DIR_ABS

# agregando logger para seguimiento de la carga de datos

# === Configuración inicial ===
FECHA_LOG = datetime.now().strftime("logs_%d_%m_%y_%H_%M")
FECHA_CSV = datetime.now().strftime("csv_%d_%m_%y_%H_%M")

from pathlib import Path

LOG_DIR_FINAL = LOG_DIR_ABS / FECHA_LOG
CSV_DIR_FINAL = LOG_DIR_ABS / FECHA_CSV

def preparar_ruta(base_dir: Path, nombre_archivo: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / nombre_archivo

NIVEL_POR_DEFECTO = "INFO"

def nivel_de_logger(nombre_logger: str) -> int:
    """Nivel de un logger según el .env.

    Prioridad: LOG_LEVEL_<NOMBRE_EN_MAYUSCULAS> > LOG_LEVEL > INFO.
    Ejemplo: LOG_LEVEL_CARGA_DB=DEBUG
    """
    valor = (
        os.getenv(f"LOG_LEVEL_{nombre_logger.upper()}")
        or os.getenv("LOG_LEVEL")
        or NIVEL_POR_DEFECTO
    )

    # El módulo logging almacena los niveles como enteros (ej. DEBUG=10, INFO=20).
    # getattr busca dinámicamente la constante; si no existe (ej. error de tipeo), 
    # devuelve None en lugar de romper la ejecución.
    nivel = getattr(logging, valor.strip().upper(), None)

    # Validación defensiva: si el valor recuperado no es un entero válido,
    # se aplica un respaldo seguro a INFO.
    return nivel if isinstance(nivel, int) else logging.INFO


def setup_logger(nombre_logger, nombre_archivo):
    logger = logging.getLogger(nombre_logger)
    ruta_log = (Path(LOG_DIR_FINAL) / nombre_archivo).resolve()

    if logger.handlers:
        # el logger ya existe: comprobar que escribe en el mismo archivo
        for h in logger.handlers:
            if isinstance(h, logging.FileHandler) and Path(h.baseFilename) != ruta_log:
                raise ValueError(
                    f"El logger '{nombre_logger}' ya escribe en '{Path(h.baseFilename).name}' "
                    f"y se pidió '{nombre_archivo}'. Usá otro nombre de logger."
                )
        return logger

    preparar_ruta(LOG_DIR_FINAL, nombre_archivo)   # crea la carpeta si falta
    logger.setLevel(nivel_de_logger(nombre_logger))
    file_handler = logging.FileHandler(ruta_log, mode='a', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger

def guardar_pregunta_y_respuestas_en_log(pregunta, numero_pregunta, nombre_archivo):
    ruta = preparar_ruta(LOG_DIR_FINAL,nombre_archivo)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write("═══════════════════════════════════════════════════════\n")
        f.write(f"[PREGUNTA {numero_pregunta}]\n")
        f.write(pregunta.contenido + "\n")
        f.write(pregunta.timestamp + "\n")
        f.write("\n[RESPUESTAS]\n")
        if pregunta.respuestas:
            for idx, respuesta in enumerate(pregunta.respuestas, start=1):
                f.write(f"  → Fecha de Respuesta {idx}: {respuesta.timestamp}\n")
                f.write(f"      → Autor Respuesta {idx}: {respuesta.autor}\n")
                f.write(f"          → Respuesta {idx}: {respuesta.contenido}\n")
        else:
            f.write("⚠️ No hubo respuestas para esta pregunta.\n")
        f.write("═══════════════════════════════════════════════════════\n\n")


def guardar_resultados_en_csvs(df_filtrado, filtros_aplicados, nombre_base):   
    nombre_archivo_filtrado = f"{nombre_base}_filtrado_limpio.csv"
    ruta_salida_filtrado = preparar_ruta(CSV_DIR_FINAL, nombre_archivo_filtrado)

    fila_conteo = pd.DataFrame({ col: [""] for col in df_filtrado.columns})
    fila_conteo.iloc[0, 0] = (f"Cantidad de registros: {len(df_filtrado)}")
    df_filtrado_con_resumen = pd.concat([df_filtrado, fila_conteo], ignore_index=True)

    df_filtrado_con_resumen.to_csv(ruta_salida_filtrado, index=False, encoding="utf-8")
    
    for nombre_filtro, df_subfiltrado in filtros_aplicados.items():
        nombre_archivo = f"{nombre_base}_{nombre_filtro}.csv"
        ruta_final = preparar_ruta(CSV_DIR_FINAL, nombre_archivo)
        
        if df_subfiltrado.empty:
            mensaje = pd.DataFrame({"info": [f"No se encontraron mensajes que cumplan con el filtro: {nombre_filtro}"]})
            mensaje.to_csv(ruta_final, index=False, encoding="utf-8")
        else:
            fila_conteo = pd.DataFrame({
                col: [""] for col in df_subfiltrado.columns 
            })
            fila_conteo.iloc[0, 0] = f"Cantidad de registros: {len(df_subfiltrado)}" 
            
            df_con_fila_extra = pd.concat([df_subfiltrado, fila_conteo], ignore_index=True)
            df_con_fila_extra.to_csv(ruta_final, index=False, encoding="utf-8")

def guardar_pregunta(pregunta, numero_pregunta, ruta_archivo):
    ruta = preparar_ruta(LOG_DIR_FINAL,ruta_archivo)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write("═══════════════════════════════════════════════════════\n")
        f.write(f"[PREGUNTA {numero_pregunta}]\n")
        f.write(pregunta+ "\n")
        f.write("═══════════════════════════════════════════════════════\n\n")

