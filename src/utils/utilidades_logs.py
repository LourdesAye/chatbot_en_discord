import logging
import os
from datetime import datetime

import pandas as pd

from utils.config_paths import LOG_DIR_ABS

# agregando logger para seguimiento de la carga de datos

# === Configuración inicial ===
FECHA_LOG = datetime.now().strftime("logs_%d_%m_%y_%H_%M")
FECHA_CSV = datetime.now().strftime("csv_%d_%m_%y_%H_%M")

LOG_DIR_FINAL = os.path.join(LOG_DIR_ABS, FECHA_LOG)
CSV_DIR_FINAL = os.path.join(LOG_DIR_ABS, FECHA_CSV)

def preparar_ruta(base_dir, nombre_archivo):
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, nombre_archivo)

def setup_logger(nombre_logger, nombre_archivo):
    ruta_log = preparar_ruta(LOG_DIR_FINAL,nombre_archivo)
    logger = logging.getLogger(nombre_logger)  # Cada proceso tiene su propio logger
    
    if not logger.handlers:  # Para evitar handlers duplicados
        logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(ruta_log, mode='a', encoding='utf-8') # Creación de FileHandler
        
        # Forzar a que haga flush de manera automática después de cada mensaje (.emit)
        # Pisar el método emit original para asegurar de que siempre se limpie el búfer
        # esto evita que si una operación es muy rápida de manera que se cierra la ejecución, 
        # python no pierde el buffer de mensajes logs que aun no llegaron a escribirse
        original_emit = file_handler.emit
        def auto_flush_emit(record):
            original_emit(record)
            file_handler.flush()
        file_handler.emit = auto_flush_emit
        
    
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False # evitar que se muestre por consola  
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

