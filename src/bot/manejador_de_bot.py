import asyncio
import logging
import os
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv
from psycopg2 import connect
from psycopg2.extras import DictCursor

from database.clase_cargar_bdd import GestorBD
from database.models.clase_mensajes import Mensaje
from embeddings.gestor_vectores import GestorBaseVectorial
from embeddings.modelo_embeddings import crear_modelo_embeddings
from processing.procesamiento_tiempo_real import ProcesadorTiempoReal
from rag.generador_respuestas import (
    ClienteOllama,
    ConversacionRecuperada,
    GeneradorRespuestasRAG,
    RespuestaHistorica,
    recortar,
)
from utils.config_paths import LOG_DIR_ABS
from utils.conexion_bdd import CONFIG
from utils.filtros_de_mensajes import (
    FiltroContenidoIrrelevanteVisual,
    FiltroContenidoVacio,
    FiltroSoloNumerosSignos,
    FiltroSoloSimbolos,
)
from utils.utilidades_logs import setup_logger
from validador import Validador

QUERY_RESPUESTAS_A_PREGUNTA = """
    SELECT
        p.texto AS pregunta,
        r.texto AS respuesta,
        r.orden,
        r.es_validada,
        r.es_corta,
        a.nombre_autor,
        a.es_docente
    FROM preguntas p
    JOIN respuestas r ON r.pregunta_id = p.id_pregunta
    JOIN mensajes m ON m.id_mensaje = r.mensaje_id
    JOIN autores a ON a.id_autor = m.autor_id
    WHERE p.id_pregunta = %s
    ORDER BY r.orden NULLS LAST, r.id_respuesta;
"""


def _lista_desde_env(valor: str | None, convertir=str) -> list:
    """'a, b,,c' -> ['a', 'b', 'c'] (ignora vacíos)."""
    return [convertir(x.strip()) for x in (valor or "").split(",") if x.strip()]


class DiscordChatbot:
    """Encapsula la lógica del funcionamiento del chatbot en Discord."""

    def __init__(self, validador: Validador):

        self.validador = validador
        load_dotenv()

        self.token = os.getenv('DISCORD_TOKEN')
        self.nombre_canal_del_chatbot = os.getenv('NOMBRE_CANAL_CHATBOT')
        id_canal = os.getenv('ID_CANAL_CHATBOT')
        self.id_canal_chatbot = int(id_canal) if id_canal and id_canal.strip() else None

        # Canales donde los alumnos hacen consultas y los docentes responden (aprendizaje en tiempo real)
        self.canales_de_consultas = _lista_desde_env(os.getenv("CANALES_DE_CONSULTAS_ALUMNOS"))
        self.ids_canales_de_consultas = _lista_desde_env(os.getenv("ID_CANALES_DE_CONSULTAS_ALUMNOS"), int)

        fecha_discord_log = datetime.now().strftime("log_discord_%d_%m_%y_%H_%M")
        archivo_log_discord = os.path.join(LOG_DIR_ABS, fecha_discord_log)
        self.discord_handler = logging.FileHandler(filename=archivo_log_discord, encoding='utf-8', mode='w')

        self.logger_chatbot_discord = setup_logger('chatbot_con_discord', 'log_chatbot_integracion_discord.txt')

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True

        self.bot = commands.Bot(command_prefix="", intents=intents)
        self.setup_events()

        modelo = crear_modelo_embeddings()
        self.logger_chatbot_discord.info(f"🧩 Modelo de embeddings: {getattr(modelo, 'model_name', '?')}")
        self.gestor_vectorial = GestorBaseVectorial(modelo)
        self.gestor_vectorial.crear_si_no_existe()

        # --- RAG con modelo local (Ollama) ---
        self.umbral_similitud = float(os.getenv("RAG_UMBRAL_SIMILITUD") or 0.0)
        self.generador_rag = None
        if (os.getenv("RAG_HABILITADO") or "true").strip().lower() in ("1", "true", "si", "sí", "yes"):
            self.generador_rag = GeneradorRespuestasRAG(ClienteOllama(), embeddings=modelo)
            ok, detalle = self.generador_rag.cliente.verificar()
            if ok:
                self.logger_chatbot_discord.info(f"✅ Ollama listo con el modelo {self.generador_rag.cliente.modelo}")
            else:
                self.logger_chatbot_discord.warning(f"⚠️ {detalle} Se responderá con la respuesta histórica sin generar.")
        else:
            self.logger_chatbot_discord.info("ℹ️ RAG deshabilitado: se responde con la respuesta histórica.")
        if self.generador_rag:
            self.logger_chatbot_discord.info(f"🧪 Modo RAG: {self.generador_rag.modo} (apoyo mínimo {self.generador_rag.min_apoyo})")
        # una sola generación a la vez: evita saturar la notebook
        self._semaforo_llm = asyncio.Semaphore(1)

        # --- Procesamiento en tiempo real ---
        self.filtros_mensajes = [
            FiltroContenidoVacio(),
            FiltroContenidoIrrelevanteVisual(),
            FiltroSoloNumerosSignos(),
            FiltroSoloSimbolos(),
        ]
        self.procesador_tiempo_real = None
        self._lock_tiempo_real = asyncio.Lock()  # los mensajes se procesan de a uno y en orden
        if self.canales_de_consultas or self.ids_canales_de_consultas:
            self.gestor_bd_tiempo_real = GestorBD(CONFIG, validador)
            self.procesador_tiempo_real = ProcesadorTiempoReal(
                "log_tiempo_real", validador, self.gestor_bd_tiempo_real, self.gestor_vectorial
            )
            self.logger_chatbot_discord.info(
                f"✅ Tiempo real activo en canales: {self.canales_de_consultas} / ids: {self.ids_canales_de_consultas}"
            )

    # ------------------------------------------------------------------
    # Consulta del alumno: búsqueda semántica + RAG
    # ------------------------------------------------------------------
    def obtener_interaccion_completa_pregunta_respuestas(self, query, id_pregunta):
        conn = connect(**CONFIG)
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(query, (id_pregunta,))
        datos = cursor.fetchall()
        cursor.close()
        conn.close()
        return datos

    def formar_mensaje_discord(self, pregunta, filas):
        mensaje = f"**Pregunta original:**\n>{pregunta}\n\n"
        mensaje += "**Respuestas:**\n"
        for fila in filas:
            etiqueta = "👩‍🏫 Docente" if fila["es_docente"] else "👤 Alumno"
            mensaje += (
                f"\n{etiqueta} — *{fila['nombre_autor']}*\n"
                f"{fila['respuesta']}\n"
                f"{'─' * 20}"
            )
        return mensaje

    def _texto_canal_consultas(self):
        """Mención clicable del canal de consultas de la cátedra (si se configuró su ID)."""
        id_canal = (os.getenv("ID_CANAL_CONSULTAS_CATEDRA") or "").strip()
        if id_canal.isdigit():
            return f"<#{id_canal}>"
        return "el canal de consultas de la cátedra de Diseño de Sistemas"

    def mensaje_sin_informacion(self):
        return (
            "No encontré información suficiente en las consultas anteriores para responder tu pregunta 😕. "
            f"Podés consultarlo en {self._texto_canal_consultas()}."
        )

    def mensaje_sugerencias(self, resultado):
        """Sin respuesta directa: se muestra lo más cercano que dijeron los docentes, con un aviso claro."""
        frases = "\n".join(f"• {f.texto}" for f in resultado.sugerencias)
        return (
            "**No encontré una respuesta directa a tu pregunta**, pero en consultas anteriores docentes dijeron "
            f"esto sobre temas relacionados:\n{frases}\n\n"
            "ℹ️ *Son frases que el sistema eligió automáticamente por su parecido con tu pregunta: pueden no responder "
            f"justo lo que preguntaste. Si falta información, consultá en {self._texto_canal_consultas()}.*"
        )

    def formar_mensaje_rag(self, resultado):
        canal = self._texto_canal_consultas()
        if resultado.con_ia:
            return (
                f"{resultado.texto}\n\n"
                "🤖 *Esta respuesta la redactó una inteligencia artificial usando lo que docentes respondieron "
                f"en consultas anteriores. Puede tener errores: si algo no te cierra o falta información, consultá en {canal}.*"
            )
        encabezado = (
            "**La inteligencia artificial no está disponible en este momento.** "
            "Igual te muestro lo que respondieron docentes en consultas anteriores parecidas a la tuya:"
            if resultado.degradado
            else "**Esto respondieron docentes en consultas anteriores parecidas a la tuya:**"
        )
        return (
            f"{encabezado}\n{resultado.texto}\n\n"
            "ℹ️ *No es una respuesta escrita por una IA: son frases de docentes que el sistema eligió automáticamente "
            f"por su parecido con tu pregunta. Puede que no respondan justo lo que preguntaste. Si falta información, consultá en {canal}.*"
        )

    def _recuperar_conversaciones(self, resultados):
        """Para cada pregunta parecida, trae sus respuestas de PostgreSQL. Devuelve [(conversacion, filas)]."""
        conversaciones = []
        for doc, similitud in resultados:
            id_pregunta = doc.metadata.get("id")
            if id_pregunta is None:
                continue
            filas = self.obtener_interaccion_completa_pregunta_respuestas(QUERY_RESPUESTAS_A_PREGUNTA, id_pregunta)
            if not filas:
                continue
            conversacion = ConversacionRecuperada(
                pregunta=doc.page_content,
                similitud=similitud,
                respuestas=[
                    RespuestaHistorica(
                        es_docente=bool(f["es_docente"]),
                        texto=f["respuesta"],
                        es_corta=bool(f["es_corta"]),
                    )
                    for f in filas
                ],
            )
            conversaciones.append((conversacion, filas))
        return conversaciones

    async def _enviar_en_partes(self, destino, texto, limite=1900):
        """Discord rechaza mensajes de más de 2000 caracteres: se envía en partes."""
        while texto:
            if len(texto) <= limite:
                await destino.send(texto)
                return
            corte = texto.rfind("\n", 0, limite)
            if corte <= 0:
                corte = limite
            await destino.send(texto[:corte])
            texto = texto[corte:].lstrip("\n")

    async def _procesar_y_responder_consulta(self, destino, mensaje_texto, autor_nombre):
        """Búsqueda semántica y respuesta (generada con RAG, o histórica si no hay modelo) en un canal o hilo."""
        await destino.send("🕓 Estoy procesando tu mensaje... Puede tardar un par de minutos ⏳")

        if not self.gestor_vectorial.vectordb:
            await destino.send("Todavía no tengo preguntas cargadas para buscar 😕. Intentalo más tarde")
            self.logger_chatbot_discord.debug("❌ No existe base vectorial cargada; se informa al usuario.")
            return

        resultados = await asyncio.to_thread(self.gestor_vectorial.buscar, mensaje_texto, 3)
        # Deja registradas las similitudes para poder calibrar RAG_UMBRAL_SIMILITUD
        self.logger_chatbot_discord.debug(
            f"🔎 Similitudes (umbral {self.umbral_similitud}): "
            + " | ".join(f"{sim:.3f} → {recortar(doc.page_content, 60)}" for doc, sim in (resultados or []))
        )
        resultados = [(doc, sim) for doc, sim in (resultados or []) if sim >= self.umbral_similitud]
        conversaciones = await asyncio.to_thread(self._recuperar_conversaciones, resultados) if resultados else []

        if not conversaciones:
            await destino.send(f"No encontré algo parecido en las consultas anteriores. Podés preguntar en {self._texto_canal_consultas()} 🙂")
            self.logger_chatbot_discord.debug("❌ No se encontraron preguntas parecidas; se informa al usuario.")
            return

        mensaje_para_discord = None
        if self.generador_rag:
            async with self._semaforo_llm:
                async with destino.typing():
                    resultado = await asyncio.to_thread(
                        self.generador_rag.generar, mensaje_texto, [c for c, _ in conversaciones]
                    )
            if resultado and resultado.sin_informacion:
                if resultado.sugerencias:
                    await self._enviar_en_partes(destino, self.mensaje_sugerencias(resultado))
                    self.logger_chatbot_discord.debug("ℹ️ Sin respuesta directa: se muestran las frases más cercanas de los docentes.")
                else:
                    await destino.send(self.mensaje_sin_informacion())
                    self.logger_chatbot_discord.debug("ℹ️ Sin respaldo suficiente en las consultas anteriores: no se inventa respuesta.")
                await self._cerrar_hilo_si_corresponde(destino, autor_nombre, respondida=False)
                return
            if resultado:
                mensaje_para_discord = self.formar_mensaje_rag(resultado)
            else:
                self.logger_chatbot_discord.warning("⚠️ El modelo no respondió; se usa la respuesta histórica.")

        if mensaje_para_discord is None:
            conversacion, filas = conversaciones[0]
            mensaje_para_discord = self.formar_mensaje_discord(conversacion.pregunta, filas)

        self.logger_chatbot_discord.debug(f"📩 Enviando respuesta al hilo de {autor_nombre}...")
        await self._enviar_en_partes(destino, mensaje_para_discord)
        self.logger_chatbot_discord.debug(f"✅ Respuesta enviada al hilo de {autor_nombre}.")

        await self._cerrar_hilo_si_corresponde(destino, autor_nombre)

    async def _cerrar_hilo_si_corresponde(self, destino, autor_nombre, respondida=True):
        """Cierra y archiva el hilo si el destino es un Thread."""
        if isinstance(destino, discord.Thread):
            saludo = "Tu consulta ya fue respondida 😊\n" if respondida else ""
            await destino.send(
                saludo
                + "Cerramos el hilo para mantener el canal ordenado.\n"
                "Si necesitás volver sobre el tema, abrí un hilo nuevo."
            )
            self.logger_chatbot_discord.debug(f"🔖 Cerrando hilo de {autor_nombre}...")
            await destino.edit(archived=True, locked=True)
            self.logger_chatbot_discord.debug(f"✅ Hilo de {autor_nombre} cerrado y archivado.")

    # ------------------------------------------------------------------
    # Aprendizaje en tiempo real
    # ------------------------------------------------------------------
    def _es_canal_de_consultas(self, canal):
        base = canal.parent if isinstance(canal, discord.Thread) else canal
        if base is None:
            return False
        return getattr(base, "id", None) in self.ids_canales_de_consultas \
            or getattr(base, "name", None) in self.canales_de_consultas

    async def _procesar_mensaje_tiempo_real(self, message):
        texto = (message.content or "").strip()
        if any(filtro.aplicar(texto) for filtro in self.filtros_mensajes):
            return
        mensaje = Mensaje.from_discord(message, self.validador)
        async with self._lock_tiempo_real:
            try:
                await asyncio.to_thread(self.procesador_tiempo_real.procesar_mensaje, mensaje)
            except Exception:
                self.logger_chatbot_discord.exception(f"❌ Error procesando en tiempo real el mensaje {message.id}")

    def setup_events(self):
        @self.bot.event
        async def on_ready():
            self.logger_chatbot_discord.debug(f"✅ Bot conectado como {self.bot.user}")
            for guild in self.bot.guilds:
                canal = None
                if self.id_canal_chatbot:
                    canal = self.bot.get_channel(int(self.id_canal_chatbot))
                if not canal and self.nombre_canal_del_chatbot:
                    canal = discord.utils.get(guild.text_channels, name=self.nombre_canal_del_chatbot)
                if canal:
                    await canal.send(f"🤖 ¡Bot conectado como {self.bot.user}!")
                    self.logger_chatbot_discord.debug(f"✅ Mensaje de autenticación exitosa enviado al canal #{canal.name} en {guild.name}")
                else:
                    self.logger_chatbot_discord.debug(f"❌ Canal no encontrado en el servidor: {guild.name}")

        @self.bot.event
        async def on_message(message):
            if message.author.bot:
                return

            canal = message.channel
            canal_nombre = getattr(canal, "name", "Sin nombre")

            # --- Caso 1: mensaje en el canal principal del chatbot ---
            if isinstance(canal, discord.TextChannel) and canal_nombre == self.nombre_canal_del_chatbot:
                self.logger_chatbot_discord.debug(f"📩 Nuevo mensaje en canal principal del chatbot de {message.author}: {message.content}")
                self.logger_chatbot_discord.debug(f"🔖 Creando hilo para la consulta de {message.author.display_name}...")

                autor = message.author.display_name
                mention_autor = message.author.mention

                thread = await canal.create_thread(
                    name=f"Consulta de {autor}",
                    message=message,
                    auto_archive_duration=60
                )

                await canal.send(
                    f"📬 Hola {mention_autor}! Creé un hilo para tu consulta. "
                    "Hacé clic en él para continuar nuestra conversación."
                )

                texto = message.content or ""
                await self._procesar_y_responder_consulta(thread, texto, autor)
                return

            # --- Caso 2: mensaje dentro de un hilo del canal principal ---
            if isinstance(canal, discord.Thread) and canal.parent.name == self.nombre_canal_del_chatbot:
                autor = message.author.display_name
                texto = message.content or ""
                await self._procesar_y_responder_consulta(canal, texto, autor)
                return

            # --- Caso 3: canal de consultas de alumnos (aprendizaje en tiempo real) ---
            if self.procesador_tiempo_real and self._es_canal_de_consultas(canal):
                await self._procesar_mensaje_tiempo_real(message)
                return

            # Cualquier otro canal se ignora.

        @self.bot.event
        async def on_disconnect():
            self.logger_chatbot_discord.warning(
                f"⚠️ Bot desconectado a las {datetime.now().isoformat()}. "
                f"Guilds activos={len(self.bot.guilds)}, "
                f"latencia={getattr(self.bot, 'latency', None)}"
            )

        @self.bot.event
        async def on_resumed():
            self.logger_chatbot_discord.info(
                f"🔄 Bot reconectado a las {datetime.now().isoformat()}. "
                f"Guilds activos={len(self.bot.guilds)}, "
                f"latencia={getattr(self.bot, 'latency', None)}"
            )

    def run(self):
        self.bot.run(self.token, log_handler=self.discord_handler, log_level=logging.DEBUG)
