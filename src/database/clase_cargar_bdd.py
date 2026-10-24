import traceback

from dateutil.parser import isoparse
from psycopg2 import InterfaceError, OperationalError
from psycopg2.extras import RealDictCursor

from database.conector_bdd import ConectarBD
from database.models.clase_preguntas import Pregunta
from database.models.clase_respuestas import Respuesta
from utils.utilidades_logs import guardar_pregunta_y_respuestas_en_log, setup_logger
from validador import Validador

# agregando logger para seguimiento de la carga de datos
logger_db = setup_logger("carga_db", "log_persistencia_de_datos.txt")


class GestorBD:
    def __init__(self, config,validador: Validador):
        self.config = config
        self.validador = validador
        self.conector_a_base_de_datos = ConectarBD(config)
        self.conexion_bdd = self.conector_a_base_de_datos.conectar_a_base_de_datos_existente()

    def es_docente(self, nombre_usuario):
        return nombre_usuario in self.validador.obtener_docentes()

    def tiene_preguntas(self):
        with self.conexion_bdd.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM preguntas")
            cantidad = cur.fetchone()[0]
            return cantidad > 0

    def insertar_o_obtener_autor(self, nombre_autor):
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id_autor FROM autores WHERE nombre_autor = %s", (nombre_autor,)
            )
            fila = cur.fetchone()
            if fila:
                logger_db.debug(f"El autor {nombre_autor} existe en la base de datos")
                return fila["id_autor"]
            logger_db.debug(
                f"El autor {nombre_autor} NO existe en la base de datos, se lo va a ingresar"
            )
            cur.execute(
                """
                INSERT INTO autores (nombre_autor, es_docente)
                VALUES (%s, %s) RETURNING id_autor
                """,
                (nombre_autor, self.es_docente(nombre_autor)),
            )
            return cur.fetchone()["id_autor"]

    def insertar_mensaje(
        self,
        id_mensaje_discord,
        autor_id,
        fecha_mensaje,
        contenido,
        es_pregunta=False,
        origen=None,
    ):
        tipo_mensaje = "PREGUNTA" if es_pregunta else "RESPUESTA"
        logger_db.debug(
            f"Se va a ingresar un mensaje ({tipo_mensaje}) a la base de datos : {contenido}"
        )
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO mensajes (
                    id_mensaje_discord,
                    autor_id,
                    fecha_mensaje,
                    contenido,
                    es_pregunta,
                    origen
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id_mensaje
                """,
                (
                    id_mensaje_discord,
                    autor_id,
                    fecha_mensaje,
                    contenido,
                    es_pregunta,
                    origen,
                ),
            )
            return cur.fetchone()["id_mensaje"]

    def insertar_attachment(self, mensaje_id, nombre_archivo, tipo_archivo):
        logger_db.debug(
            f"se inserta un nuevo archivo adjunto llamado { nombre_archivo} asociado al mensaje {mensaje_id}"
        )
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO adjuntos (mensaje_id, url, tipo)
                VALUES (%s, %s, %s)
                RETURNING id_adjunto
                """,
                (mensaje_id, nombre_archivo, tipo_archivo),
            )
            return cur.fetchone()["id_adjunto"]

    def insertar_pregunta(self, pregunta: Pregunta, id_mensaje):
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO preguntas (mensaje_id, texto, esta_cerrada, sin_contexto, es_administrativa)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_pregunta
                """,
                (
                    id_mensaje,
                    pregunta.contenido,
                    pregunta.cerrada,
                    pregunta.sin_contexto,
                    pregunta.es_administrativa,
                ),
            )
            return cur.fetchone()["id_pregunta"]

    def insertar_respuesta(self, respuesta: Respuesta, mensaje_id, pregunta_id, orden):
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO respuestas (mensaje_id, pregunta_id, texto, orden, es_validada, es_corta)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id_respuesta
                """,
                (
                    mensaje_id,
                    pregunta_id,
                    respuesta.contenido,
                    orden,
                    respuesta.es_validada,
                    respuesta.es_corta,
                ),
            )
            return cur.fetchone()["id_respuesta"]

    def convertir_a_datetime(self, timestamp_str):
        return isoparse(timestamp_str)

    def persistir_preguntas(self, preguntas_cerradas: list[Pregunta], index):
        logger_db.debug("🗄️ Persistencia de datos")
        logger_db.debug(f"📁 se va a procesar en JSON {index} ... ")
        cont_preg_sin_resp = 0
        nombre_ruta = f"log_preg_sin_respuestas_{index}"
        preguntas_a_persistir = []

        for indice, pregunta in enumerate(preguntas_cerradas, start=1):
            if len(pregunta.respuestas) == 0:
                cont_preg_sin_resp = cont_preg_sin_resp + 1
                self.guardar_pregunta_sin_respuesta_en_log(
                    pregunta, indice, nombre_ruta, cont_preg_sin_resp
                )
            else:
                preguntas_a_persistir.append(pregunta)

        ruta_preg_persistidas = f"log_preguntas_efectivamente_pesistidas_{index}.txt"
        logger_db.debug(
            f"🗄️ Se van a persistir {len(preguntas_a_persistir)} preguntas cerradas"
        )

        try:
            mensajes_persistidos = {}
            for idx, pregunta in enumerate(preguntas_a_persistir, start=1):
                guardar_pregunta_y_respuestas_en_log(
                    pregunta, idx, ruta_preg_persistidas
                )

                logger_db.debug(
                    f"\n📌 [{idx}/{len(preguntas_a_persistir)}] Procesando un mensaje que es pregunta: \n{pregunta.contenido}\n Autor: {pregunta.autor}"
                )


                autor_id = self.insertar_o_obtener_autor(pregunta.autor)
                logger_db.debug(f"👤 Se obtuvo un el id para el autor: {autor_id} \n")

                # PERSISTIR MENSAJE DE LA PREGUNTA
                mensaje_id = self.insertar_mensaje(
                    id_mensaje_discord=pregunta.id_pregunta,
                    autor_id=autor_id,
                    fecha_mensaje=pregunta.timestamp,
                    contenido=pregunta.contenido,
                    es_pregunta=True,
                    origen=pregunta.origen,
                )
                logger_db.debug(
                    f"✉️ se obtuvo un mensaje_id (para la pregunta): {mensaje_id}"
                )

                # Guardar la relación ID de Discord -> ID interno de la BD
                mensajes_persistidos[pregunta.id_pregunta] = mensaje_id

                for nombre_archivo, tipo in pregunta.attachments:
                    self.insertar_attachment(mensaje_id, nombre_archivo, tipo)

                logger_db.debug(
                    "📁 Se insertaron en la base de datos los nombres archivos adjuntos asociados"
                )

                id_pregunta = self.insertar_pregunta(pregunta, mensaje_id)
                logger_db.debug("💾 Se persiste pregunta en la base de datos")

                logger_db.debug("📩 Se ordenan sus respuestas para ser persistidas")
                
                # PERSISTIR RESPUESTAS
                respuestas_ordenadas = sorted(
                    pregunta.respuestas,
                    key=lambda r: self.convertir_a_datetime(r.timestamp),
                )

                for orden, respuesta in enumerate(respuestas_ordenadas, start=1):
                    logger_db.debug("")
                    logger_db.debug(f"📩 respuesta {orden} : {respuesta.contenido}")
                    
                    autor_id_r = self.insertar_o_obtener_autor(respuesta.autor)
                    id_mensaje_discord = respuesta.id_respuesta
                    # ¿Este mensaje de Discord ya fue persistido?
                    if id_mensaje_discord in mensajes_persistidos:
                        # Ya existe en la tabla mensajes. Reutilizamos su ID interno.
                        mensaje_id_r = mensajes_persistidos[id_mensaje_discord]
                    else:
                        # Es la primera vez que se encuentra este mensaje. Se inserta en la tabla mensajes.
                        mensaje_id_r = self.insertar_mensaje(
                        id_mensaje_discord=respuesta.id_respuesta,
                        autor_id=autor_id_r,
                        fecha_mensaje=respuesta.timestamp,
                        contenido=respuesta.contenido,
                        es_pregunta=False,
                        origen=respuesta.origen,)
                        logger_db.debug( f"✉️ se obtuvo un mensaje_id (para la respuesta): {mensaje_id_r}")
                        # Guardar el ID para futuras asociaciones.
                        mensajes_persistidos[id_mensaje_discord] = mensaje_id_r
                    
                        for nombre_archivo, tipo in respuesta.attachments:
                            self.insertar_attachment(mensaje_id_r, nombre_archivo, tipo)
                        logger_db.debug( "📁 Se insertaron en la base de datos los nombres archivos adjuntos asociados")

                        # CREAR LA ASOCIACIÓN MENSAJE <-> PREGUNTA 
                    self.insertar_respuesta(respuesta, mensaje_id_r, id_pregunta, orden)
                    logger_db.debug("💾 Se persiste la repuesta en la base de datos")
            
            # Commit exitoso por bloque de archivo JSON procesado
            self.conexion_bdd.commit()
            logger_db.info( f"✅ Transacción confirmada exitosamente para el JSON {index}.")

        except Exception as e:
            logger_db.error(f"❌ Error al persistir las preguntas y respuestas: {e}")
            logger_db.error(traceback.format_exc())
            if self.conexion_bdd:
                self.conexion_bdd.rollback()
                logger_db.warning("⛔ Transacción revertida debido al error.")
            raise e  # Relanzamos para que el script principal sepa que falló

    # ------------------------------------------------------------------
    # Persistencia incremental (tiempo real)
    # ------------------------------------------------------------------
    def _asegurar_conexion(self):
        if self.conexion_bdd is None or self.conexion_bdd.closed:
            logger_db.warning("🔌 Reconectando a la base de datos...")
            self.conexion_bdd = self.conector_a_base_de_datos.conectar_a_base_de_datos_existente()

    def _rollback_seguro(self):
        try:
            self.conexion_bdd.rollback()
        except Exception:
            pass

    def _ejecutar_con_reintento(self, funcion, *args):
        """Ejecuta una operación; si la conexión se cayó, reconecta y reintenta una vez."""
        for intento in (1, 2):
            self._asegurar_conexion()
            try:
                return funcion(*args)
            except (OperationalError, InterfaceError) as e:
                logger_db.warning(f"⚠️ Conexión perdida (intento {intento}): {e}")
                try:
                    self.conexion_bdd.close()
                except Exception:
                    pass
                if intento == 2:
                    raise

    def buscar_mensaje_por_id_discord(self, id_mensaje_discord):
        with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id_mensaje FROM mensajes WHERE id_mensaje_discord = %s ORDER BY id_mensaje LIMIT 1",
                (id_mensaje_discord,),
            )
            fila = cur.fetchone()
            return fila["id_mensaje"] if fila else None

    def _obtener_o_insertar_mensaje_respuesta(self, respuesta: Respuesta):
        existente = self.buscar_mensaje_por_id_discord(respuesta.id_respuesta)
        if existente:
            return existente
        autor_id = self.insertar_o_obtener_autor(respuesta.autor)
        mensaje_id = self.insertar_mensaje(
            id_mensaje_discord=respuesta.id_respuesta,
            autor_id=autor_id,
            fecha_mensaje=respuesta.timestamp,
            contenido=respuesta.contenido,
            es_pregunta=False,
            origen=respuesta.origen,
        )
        for nombre_archivo, tipo in respuesta.attachments:
            self.insertar_attachment(mensaje_id, nombre_archivo, tipo)
        return mensaje_id

    def persistir_pregunta_tiempo_real(self, pregunta: Pregunta) -> int:
        """Persiste UNA pregunta cerrada con sus respuestas y devuelve su id en la base."""
        return self._ejecutar_con_reintento(self._persistir_pregunta_tiempo_real, pregunta)

    def _persistir_pregunta_tiempo_real(self, pregunta: Pregunta) -> int:
        try:
            autor_id = self.insertar_o_obtener_autor(pregunta.autor)
            mensaje_id = self.insertar_mensaje(
                id_mensaje_discord=pregunta.id_pregunta,
                autor_id=autor_id,
                fecha_mensaje=pregunta.timestamp,
                contenido=pregunta.contenido,
                es_pregunta=True,
                origen=pregunta.origen,
            )
            for nombre_archivo, tipo in pregunta.attachments:
                self.insertar_attachment(mensaje_id, nombre_archivo, tipo)
            id_pregunta = self.insertar_pregunta(pregunta, mensaje_id)
            respuestas_ordenadas = sorted(
                pregunta.respuestas, key=lambda r: self.convertir_a_datetime(r.timestamp)
            )
            for orden, respuesta in enumerate(respuestas_ordenadas, start=1):
                mensaje_id_r = self._obtener_o_insertar_mensaje_respuesta(respuesta)
                self.insertar_respuesta(respuesta, mensaje_id_r, id_pregunta, orden)
            self.conexion_bdd.commit()
            logger_db.info(f"✅ Pregunta {id_pregunta} persistida en tiempo real")
            return id_pregunta
        except Exception:
            self._rollback_seguro()
            raise

    def persistir_respuesta_tardia(self, id_pregunta_bd: int, respuesta: Respuesta):
        """Agrega una respuesta a una pregunta que ya estaba cerrada y persistida."""
        return self._ejecutar_con_reintento(self._persistir_respuesta_tardia, id_pregunta_bd, respuesta)

    def _persistir_respuesta_tardia(self, id_pregunta_bd: int, respuesta: Respuesta):
        try:
            with self.conexion_bdd.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(orden), 0) + 1 AS siguiente FROM respuestas WHERE pregunta_id = %s",
                    (id_pregunta_bd,),
                )
                orden = cur.fetchone()["siguiente"]
            mensaje_id_r = self._obtener_o_insertar_mensaje_respuesta(respuesta)
            self.insertar_respuesta(respuesta, mensaje_id_r, id_pregunta_bd, orden)
            self.conexion_bdd.commit()
            logger_db.info(f"✅ Respuesta tardía agregada a la pregunta {id_pregunta_bd}")
        except Exception:
            self._rollback_seguro()
            raise

    def cerrar_conexion(self):
        try:
            if self.conexion_bdd and not self.conexion_bdd.closed:
                self.conexion_bdd.commit()
                self.conexion_bdd.close()
                logger_db.info(
                    "🔌 Conexión con la base de datos cerrada correctamente."
                )
        except Exception as e:
            logger_db.error(f"Error al cerrar la conexión a la base de datos: {e}")
