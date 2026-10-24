"""Simula una conversación de tiempo real SIN Discord.

Sirve para probar la persistencia en PostgreSQL y la indexación en ChromaDB cuando no se
puede participar como alumno y como docente a la vez. Usa la base real configurada en el .env:
los datos de prueba quedan guardados.

Ejecutar desde la raíz del proyecto:  python src/probar_tiempo_real.py
"""
import time
from datetime import datetime, timedelta, timezone

from configuracion.repository import RepositorioYAML
from database.clase_cargar_bdd import GestorBD
from database.models.clase_mensajes import Mensaje
from embeddings.gestor_vectores import GestorBaseVectorial
from embeddings.modelo_embeddings import crear_modelo_embeddings
from processing.procesamiento_tiempo_real import ProcesadorTiempoReal
from utils.conexion_bdd import CONFIG
from validador import Validador

PREGUNTA = "Hola, ¿para qué sirve el patrón Observer en un sistema de notificaciones?"


def main():
    validador = Validador(RepositorioYAML())
    docente = sorted(validador.obtener_docentes())[0]  # un docente cualquiera de docentes.yaml
    alumno = "alumno_de_prueba"

    gestor_vectorial = GestorBaseVectorial(crear_modelo_embeddings())
    gestor_vectorial.crear_si_no_existe()
    gestor_bd = GestorBD(CONFIG, validador)
    procesador = ProcesadorTiempoReal("log_prueba_tiempo_real", validador, gestor_bd, gestor_vectorial)

    conversacion = [
        (alumno, PREGUNTA),
        (docente, "Sirve para que varios objetos se enteren automáticamente cuando cambia el estado de otro, sin acoplarlos entre sí."),
        (alumno, "Perfecto, gracias!"),
    ]

    base_id = int(time.time() * 1000)
    inicio = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i, (autor, texto) in enumerate(conversacion):
        mensaje = Mensaje(
            id_mensaje=base_id + i,
            autor=autor,
            contenido=texto,
            timestamp=(inicio + timedelta(minutes=i)).isoformat(),
            attachments=[],
            origen="prueba_tiempo_real",
            validador=validador,
        )
        rol = "DOCENTE" if mensaje.es_autor_docente() else "ALUMNO"
        print(f"→ [{rol}] {autor}: {texto}")
        procesador.procesar_mensaje(mensaje)

    cerradas = procesador.preguntas_cerradas
    if not cerradas:
        print("\n❌ La pregunta no se cerró. Revisá logs/ (log_procesamiento_tiempo_real.txt).")
        return
    pregunta = cerradas[-1]
    print(f"\n✅ Pregunta cerrada y guardada en PostgreSQL (id_pregunta = {pregunta.id_pregunta_bd})")
    print(f"   sin_contexto={pregunta.sin_contexto} | administrativa={pregunta.es_administrativa} | respuestas={len(pregunta.respuestas)}")
    if procesador.contador_preguntas_indexadas:
        print("✅ Indexada en la base vectorial: ya puede encontrarla el chatbot.")
        print("   Probá en el canal del chatbot: «¿Para qué sirve el patrón Observer?»")
    else:
        print("⚠️ No se indexó (sin contexto, administrativa o sin respuesta de docente).")


if __name__ == "__main__":
    main()
