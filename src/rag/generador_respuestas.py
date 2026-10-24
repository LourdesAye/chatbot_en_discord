"""RAG local con respuestas fundamentadas.

Flujo:
  1. Del conjunto de conversaciones recuperadas se toman las respuestas de los docentes, se dividen en
     oraciones y se eligen las pocas más relacionadas con la consulta (contexto corto = respuesta más rápida).
  2. Esas oraciones se numeran como fragmentos y el modelo (Ollama) debe responder citando el número
     del fragmento que respalda cada oración.
  3. El código verifica la respuesta: descarta toda oración sin cita o cuyas palabras no aparecen en el
     fragmento citado. Si no queda nada, el bot responde que no tiene información (no inventa).
"""
import os
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import requests

from utils.utilidades_logs import setup_logger

logger_rag = setup_logger("rag_ollama", "log_rag_ollama.txt")

URL_OLLAMA_POR_DEFECTO = "http://localhost:11434"
MODELO_POR_DEFECTO = "qwen2.5:3b"
MARCA_SIN_INFORMACION = "SIN_INFORMACION"

PROMPT_SISTEMA = (
    "Sos el asistente de la materia Diseño de Sistemas. "
    "Vas a recibir fragmentos numerados con respuestas de docentes a consultas anteriores y la consulta de un alumno. "
    "Respondé SOLO con información que figure en los fragmentos: no uses conocimiento propio ni agregues definiciones generales. "
    "Cada oración de tu respuesta debe terminar con el número del fragmento que la respalda, por ejemplo [1] o [2][3]. "
    "Los fragmentos pueden venir de trabajos de otros alumnos: no presentes ejemplos de otros trabajos como si fueran del alumno que consulta. "
    f"Si los fragmentos no responden la consulta, respondé únicamente con la palabra {MARCA_SIN_INFORMACION}. "
    "Respondé en español, en un máximo de 4 oraciones.\n\n"
    "Ejemplo de formato:\n"
    "Fragmentos:\n[1] El semáforo cambia de rojo a verde cuando termina el temporizador.\n"
    "Consulta del alumno: ¿Cuándo cambia el semáforo?\n"
    "Respuesta: Cambia de rojo a verde cuando termina el temporizador [1]."
)

PALABRAS_VACIAS = {
    "para", "como", "esta", "este", "esto", "estos", "estas", "pero", "porque", "cuando", "donde", "entre",
    "sobre", "desde", "hasta", "tambien", "tiene", "tienen", "hace", "hacer", "puede", "pueden", "cada",
    "unos", "unas", "algo", "todo", "todos", "solo", "pero", "tambien", "mismo", "misma", "otra", "otro",
    "otros", "otras", "debe", "deben", "segun", "luego", "antes", "despues", "sino", "aunque", "ademas",
    "entonces", "respecto", "manera", "forma", "caso", "casos", "parte", "tipo", "veces", "dicho", "dicha",
    "ustedes", "nosotros", "ellos", "ellas", "algun", "alguna", "bien", "aqui", "tambien", "sera", "seria",
    "podria", "estan", "estar", "hola", "gracias", "buenas", "buenos", "saludos",
}
FRASES_DE_CORTESIA = (
    "cualquier cosa avis", "espero que se haya entendido", "saludos", "mil disculpas", "gracias",
    "buenas noches", "buenos dias", "buenas tardes", "disculpa",
)


@dataclass
class RespuestaHistorica:
    es_docente: bool
    texto: str
    es_corta: bool = False


@dataclass
class ConversacionRecuperada:
    pregunta: str
    similitud: float = 0.0
    respuestas: list[RespuestaHistorica] = field(default_factory=list)


@dataclass
class Fragmento:
    numero: int
    texto: str
    puntaje: float = 0.0


@dataclass
class ResultadoRAG:
    texto: str                      # respuesta final (ya verificada)
    sin_informacion: bool           # True: no hay respaldo suficiente, el bot no debe inventar
    con_ia: bool                    # False en modo extractivo (frases textuales de los docentes)
    fragmentos: list[Fragmento] = field(default_factory=list)
    degradado: bool = False         # True si se esperaba la IA pero no respondió (se muestran frases de los docentes)
    sugerencias: list[Fragmento] = field(default_factory=list)   # lo más cercano, si no hay respuesta directa


# ----------------------------------------------------------------------------
# Utilidades de texto
# ----------------------------------------------------------------------------
def recortar(texto: str, maximo: int) -> str:
    """Recorta sin cortar palabras a la mitad."""
    texto = " ".join(texto.split())
    if len(texto) <= maximo:
        return texto
    corte = texto.rfind(" ", 0, maximo)
    return texto[: corte if corte > maximo // 2 else maximo].rstrip(" ,;:") + "…"


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower()


def palabras_clave(texto: str) -> set[str]:
    """Raíces (6 letras) de las palabras con contenido: sirven para comparar textos sin importar la flexión."""
    palabras = re.findall(r"[a-z0-9ñ]+", normalizar(texto))
    return {p[:6] for p in palabras if len(p) >= 4 and p not in PALABRAS_VACIAS}


def dividir_en_oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?…])\s+|\n+", texto) if o.strip()]


def es_sin_informacion(texto: str) -> bool:
    """True si el modelo indicó que los fragmentos no alcanzan (respuesta corta con la marca)."""
    normalizado = texto.strip().upper().replace(" ", "_")
    return MARCA_SIN_INFORMACION in normalizado and len(normalizado) <= 60


# ----------------------------------------------------------------------------
# Cliente de Ollama
# ----------------------------------------------------------------------------
class ClienteOllama:
    """Cliente mínimo de la API HTTP de Ollama (`/api/chat`)."""

    def __init__(self, url=None, modelo=None, timeout=None,
                 temperatura=0.2, num_ctx=None, max_tokens=None, keep_alive="15m"):
        self.url = (url or os.getenv("OLLAMA_URL") or URL_OLLAMA_POR_DEFECTO).rstrip("/")
        self.modelo = modelo or os.getenv("OLLAMA_MODEL") or MODELO_POR_DEFECTO
        self.timeout = float(timeout or os.getenv("OLLAMA_TIMEOUT") or 180)
        self.temperatura = temperatura
        # tamaño de contexto y largo máximo de respuesta; bajarlos reduce memoria y tiempo
        self.num_ctx = int(num_ctx or os.getenv("OLLAMA_NUM_CTX") or 4096)
        self.max_tokens = int(max_tokens or os.getenv("OLLAMA_MAX_TOKENS") or 350)
        self.keep_alive = keep_alive

    def verificar(self) -> tuple[bool, str]:
        """Comprueba que Ollama responde y que el modelo está descargado."""
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=5)
            r.raise_for_status()
            nombres = [m.get("name", "") for m in r.json().get("models", [])]
        except (requests.RequestException, ValueError) as e:
            return False, f"No se pudo conectar con Ollama en {self.url} ({e}). ¿Está corriendo `ollama serve`?"
        if self.modelo in nombres or (":" not in self.modelo and f"{self.modelo}:latest" in nombres):
            return True, "ok"
        return False, f"El modelo '{self.modelo}' no está descargado. Ejecutá: ollama pull {self.modelo}"

    def chat(self, mensajes: list[dict]) -> str | None:
        payload = {
            "model": self.modelo,
            "messages": mensajes,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperatura,
                "num_ctx": self.num_ctx,
                "num_predict": self.max_tokens,
            },
        }
        try:
            # (timeout de conexión, timeout de lectura): falla rápido si Ollama no está levantado
            r = requests.post(f"{self.url}/api/chat", json=payload, timeout=(5, self.timeout))
            r.raise_for_status()
            contenido = (r.json().get("message") or {}).get("content", "").strip()
        except (requests.RequestException, ValueError) as e:
            logger_rag.error(f"❌ Error al llamar a Ollama: {e}")
            return None
        return contenido or None


# ----------------------------------------------------------------------------
# Generador RAG
# ----------------------------------------------------------------------------
class GeneradorRespuestasRAG:
    def __init__(self, cliente: ClienteOllama | None = None, embeddings=None,
                 max_fragmentos: int = 5, max_chars_fragmento: int = 400,
                 max_respuestas_docente: int = 2, min_apoyo: float | None = None,
                 modo: str | None = None, umbral_sugerencia: float | None = None):
        self.cliente = cliente or ClienteOllama()
        self.embeddings = embeddings  # modelo de embeddings para elegir las oraciones más relevantes
        self.max_fragmentos = max_fragmentos
        self.max_chars_fragmento = max_chars_fragmento
        # Solo las primeras respuestas de docentes: suelen ser la respuesta real a la pregunta.
        self.max_respuestas_docente = max_respuestas_docente
        # Proporción mínima de palabras de cada oración que debe aparecer en el fragmento citado
        self.min_apoyo = float(min_apoyo if min_apoyo is not None else (os.getenv("RAG_MIN_APOYO") or 0.6))
        # "generativo": el modelo redacta y el código verifica. "extractivo": sin modelo, frases textuales.
        self.modo = (modo or os.getenv("RAG_MODO") or "generativo").strip().lower()
        # Similitud mínima (misma escala que "Similitud:" de los logs) para MOSTRAR una frase de docente sin que el
        # modelo la haya verificado (modo extractivo, IA caída o "sin respuesta directa"). 1 = nunca mostrar.
        self.umbral_sugerencia = float(umbral_sugerencia if umbral_sugerencia is not None else (os.getenv("RAG_UMBRAL_SUGERENCIA") or 0.0))

    # --- 1) selección de fragmentos --------------------------------------
    def _puntuar(self, consulta: str, oraciones: list[str]) -> tuple[list[float], bool]:
        """Puntaje de cada oración respecto de la consulta. El booleano indica si fue semántico (embeddings)."""
        if self.embeddings is not None:
            try:
                vq = np.array(self.embeddings.embed_query(consulta), dtype=float)
                vs = np.array(self.embeddings.embed_documents(oraciones), dtype=float)
                vq = vq / (np.linalg.norm(vq) or 1.0)
                vs = vs / np.clip(np.linalg.norm(vs, axis=1, keepdims=True), 1e-9, None)
                return (2 * (vs @ vq) - 1).tolist(), True      # misma escala que "Similitud:" en los logs
            except Exception:
                logger_rag.exception("⚠️ Falló el ranking con embeddings; se usa coincidencia de palabras")
        q = palabras_clave(consulta)
        puntajes = []
        for o in oraciones:
            p = palabras_clave(o)
            puntajes.append(2 * len(q & p) / (len(q | p) or 1) - 1)
        return puntajes, False

    def seleccionar_fragmentos(self, consulta: str, conversaciones: list[ConversacionRecuperada]) -> list[Fragmento]:
        candidatas: list[tuple[str, int]] = []   # (oración, índice de la conversación de origen)
        vistas: set[str] = set()
        for i_conv, conv in enumerate(conversaciones):
            docentes = [r for r in conv.respuestas if r.es_docente][: self.max_respuestas_docente]
            for r in docentes:
                limpio = re.sub(r"<[@#!&]?\d+>", "", r.texto)        # menciones de Discord
                for oracion in dividir_en_oraciones(limpio):
                    oracion = re.sub(r"^\s*\d+\s*[-.)]\s*", "", oracion).strip()   # "1 - ", "2) "
                    normalizada = normalizar(oracion)
                    palabras = len(oracion.split())
                    if palabras < 5 or normalizada in vistas:
                        continue
                    # Una pregunta del docente ("¿IntelliJ te indica eso?") no aporta información
                    if oracion.endswith("?") or oracion.startswith("¿"):
                        continue
                    # Saludos y frases de relleno ("Hola Iván, trato de responder punto por punto.")
                    if palabras < 12 and re.match(r"(hola|buenas|buen dia|buenos dias)\b", normalizada):
                        continue
                    if palabras < 9 and any(f in normalizada for f in FRASES_DE_CORTESIA):
                        continue
                    # Frases con poco contenido ("Es correcto lo que planteas!")
                    if len(palabras_clave(oracion)) < 3:
                        continue
                    vistas.add(normalizada)
                    candidatas.append((recortar(oracion, self.max_chars_fragmento), i_conv))
        if not candidatas:
            return []
        puntajes, semantico = self._puntuar(consulta, [c[0] for c in candidatas])
        indices = list(range(len(candidatas)))
        if not semantico and any(p > -1 for p in puntajes):
            indices = [i for i in indices if puntajes[i] > -1]  # sin embeddings: descartar lo que no comparte palabras
        # 1) la mejor oración de cada conversación (para no depender de una sola)
        elegidos: list[int] = []
        for i_conv in range(len(conversaciones)):
            propias = [i for i in indices if candidatas[i][1] == i_conv]
            if propias:
                elegidos.append(max(propias, key=lambda i: puntajes[i]))
        # 2) completar hasta el máximo con las de mayor puntaje
        resto = sorted((i for i in indices if i not in elegidos), key=lambda i: -puntajes[i])
        elegidos = (elegidos + resto)[: self.max_fragmentos]
        elegidos.sort(key=lambda i: -puntajes[i])
        return [Fragmento(n, candidatas[i][0], float(puntajes[i])) for n, i in enumerate(elegidos, start=1)]

    # --- 2) prompt ---------------------------------------------------------
    def construir_mensajes(self, consulta: str, fragmentos: list[Fragmento]) -> list[dict]:
        bloque = "\n".join(f"[{f.numero}] {f.texto}" for f in fragmentos)
        usuario = f"Fragmentos:\n{bloque}\n\nConsulta del alumno: {consulta.strip()}"
        return [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": usuario},
        ]

    # --- 3) verificación -----------------------------------------------------
    def verificar_respuesta(self, respuesta: str, consulta: str, fragmentos: list[Fragmento]) -> tuple[str, int, int]:
        """Conserva solo las oraciones citadas y respaldadas por el fragmento que citan.

        Devuelve (texto limpio sin citas, oraciones conservadas, oraciones descartadas).
        """
        por_numero = {f.numero: f for f in fragmentos}
        patron_cita = r"\[[\d,;\s y]+\]"
        # "texto. [1]" -> "texto [1]."
        texto = re.sub(rf"([.!?…])\s*((?:{patron_cita}\s*)+)", r" \2\1", respuesta.strip())
        palabras_consulta = palabras_clave(consulta)
        conservadas, descartadas = [], 0
        for oracion in dividir_en_oraciones(texto):
            numeros = {int(n) for grupo in re.findall(r"\[([\d,;\s y]+)\]", oracion) for n in re.findall(r"\d+", grupo)}
            citados = [por_numero[n] for n in numeros if n in por_numero]
            limpia = re.sub(rf"\s*{patron_cita}", "", oracion).strip()
            limpia = re.sub(r"\s+([.!?…])", r"\1", limpia)
            # las palabras de la propia consulta no cuentan como evidencia
            propias = palabras_clave(limpia) - palabras_consulta
            if not citados or not propias:
                descartadas += 1
                logger_rag.debug(f"🚫 Oración descartada (sin cita válida o sin contenido propio): {limpia}")
                continue
            base = set().union(*(palabras_clave(f.texto) for f in citados))
            apoyo = len(propias & base) / len(propias)
            if apoyo >= self.min_apoyo:
                conservadas.append(limpia)
            else:
                descartadas += 1
                logger_rag.debug(f"🚫 Oración descartada (apoyo {apoyo:.2f} < {self.min_apoyo}): {limpia}")
        return " ".join(conservadas), len(conservadas), descartadas

    # --- flujo completo ------------------------------------------------------
    @staticmethod
    def _texto_extractivo(fragmentos: list[Fragmento]) -> str:
        return "\n".join(f"• {f.texto}" for f in fragmentos[:3])

    def _mostrables(self, fragmentos: list[Fragmento]) -> list[Fragmento]:
        """Frases suficientemente relacionadas con la consulta como para mostrarlas tal cual (máximo 3)."""
        return [f for f in fragmentos if f.puntaje >= self.umbral_sugerencia][:3]

    def generar(self, consulta: str, conversaciones: list[ConversacionRecuperada]) -> ResultadoRAG:
        """Devuelve siempre un resultado: respuesta verificada, 'sin información', o frases de los docentes."""
        fragmentos = self.seleccionar_fragmentos(consulta, conversaciones)
        logger_rag.debug(f"🧩 Fragmentos elegidos (similitud, umbral de sugerencia {self.umbral_sugerencia}): {[(f.numero, round(f.puntaje, 3), f.texto[:60]) for f in fragmentos]}")
        if not fragmentos:
            return ResultadoRAG("", True, False, [])
        mostrables = self._mostrables(fragmentos)
        if self.modo == "extractivo":
            if not mostrables:
                return ResultadoRAG("", True, False, fragmentos)
            return ResultadoRAG(self._texto_extractivo(mostrables), False, False, fragmentos)

        logger_rag.debug(f"🧠 Consulta al modelo {self.cliente.modelo} con {len(fragmentos)} fragmentos")
        bruto = self.cliente.chat(self.construir_mensajes(consulta, fragmentos))
        if not bruto:
            # Ollama apagado, sin el modelo o sin tiempo: se muestran las frases de los docentes (modo extractivo)
            logger_rag.warning("⚠️ El modelo no respondió: se muestran las frases de los docentes (modo degradado)")
            if not mostrables:
                return ResultadoRAG("", True, False, fragmentos)
            return ResultadoRAG(self._texto_extractivo(mostrables), False, False, fragmentos, degradado=True)
        logger_rag.debug(f"💬 Respuesta generada (sin verificar): {bruto}")
        if es_sin_informacion(bruto):
            return ResultadoRAG("", True, True, fragmentos, sugerencias=mostrables)
        texto, conservadas, descartadas = self.verificar_respuesta(bruto, consulta, fragmentos)
        logger_rag.debug(f"✅ Verificación: {conservadas} oraciones conservadas, {descartadas} descartadas")
        if not texto:
            return ResultadoRAG("", True, True, fragmentos, sugerencias=mostrables)
        return ResultadoRAG(texto, False, True, fragmentos)
