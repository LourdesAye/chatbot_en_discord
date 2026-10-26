# Chatbot de consultas para Discord (RAG con modelo local)

## English summary

Discord bot that answers course questions using past student–teacher conversations.
Students often ask the same questions again and again (within days or weeks, over several
months, or in later years), so the bot reuses what teachers have already answered: students get a quick reply, and teachers don't have to answer the same
question over and over.

It stores questions and answers in PostgreSQL, saves each question as an embedding in ChromaDB
to search by meaning (semantic search), and generates answers with a local LLM (Ollama).
Each sentence of the generated answer is checked against the teachers' messages, and sentences
that no teacher actually said are discarded, to avoid made-up answers.

Started as a supervised professional practice at UTN FRBA (March – July 2025) and continued
independently afterwards. The rest of this document is in Spanish.

---

## Resumen

Bot de Discord que responde consultas de estudiantes usando conversaciones previas entre
alumnos y docentes de un curso. Procesa historiales exportados en JSON, guarda las preguntas
y respuestas en PostgreSQL, las indexa con embeddings en ChromaDB y genera la respuesta con un
modelo local (Ollama), verificando que cada oración esté apoyada en lo que dijo un docente.

Comenzó como una Práctica Profesional Supervisada en la UTN FRBA y lo continué desarrollando
por mi cuenta después de terminarla (ver [Historia del proyecto](#historia-del-proyecto)).

## Problema y objetivo

En el curso, los alumnos hacen muchas consultas repetidas. Se repiten a veces al cabo de unos
días o semanas, otras después de uno o varios meses y otras en el año siguiente, y las
respuestas de los docentes quedan dispersas en el historial de Discord. Además, un docente
humano puede tardar varias horas en responder.

La idea es que el conocimiento que ya aportaron los docentes quede almacenado y disponible:

- **Para los alumnos:** pueden preguntarle al bot y recibir una respuesta relativamente
  rápida cuando se trata de una pregunta frecuente.
- **Para los docentes:** se reduce la carga de responder varias veces la misma consulta.
- **Para el curso:** el conocimiento se agrupa en un solo lugar en vez de quedar disperso, y
  el bot sigue aprendiendo de nuevas preguntas y respuestas.

## Cómo funciona

1. **Procesamiento**: se leen los mensajes del JSON, se detectan preguntas, respuestas de
   docentes y cierres de conversación.
2. **Base de datos**: las preguntas con respuesta de un docente se guardan en PostgreSQL
   (esquema gestionado con Alembic).
3. **Embeddings**: cada pregunta se indexa en ChromaDB, es decir, se convierte en un vector
   numérico que representa su significado, para poder buscar por similitud de sentido y no
   solo por palabras exactas. El modelo de embeddings es `BAAI/bge-m3` por defecto y se puede
   cambiar con la variable `EMBEDDINGS_MODELO` del `.env`.
4. **RAG**: ante una consulta nueva se buscan las preguntas más parecidas, se arma un contexto
   con las respuestas de docentes y un modelo local de Ollama redacta la respuesta. El código
   descarta las oraciones que no estén respaldadas por los fragmentos recuperados.
5. **Bot de Discord**: responde en un hilo y puede seguir aprendiendo en tiempo real de
   canales donde alumnos preguntan y docentes responden.

## Requisitos

- Python 3.11
- PostgreSQL
- [Ollama](https://ollama.com) con un modelo descargado (se probó con `qwen2.5:7b`:
  `ollama pull qwen2.5:7b`). Es opcional: con `RAG_HABILITADO=false` no se usa.
- Un bot de Discord con el intent privilegiado **Message Content** activado, y permisos para
  enviar mensajes, crear hilos públicos, enviar mensajes en hilos y administrar hilos.

## Instalación

```bash
git clone https://github.com/LourdesAye/chatbot_en_discord.git
cd chatbot_en_discord

python -m venv venv
# Windows (PowerShell): .\venv\Scripts\Activate.ps1
# Linux / macOS:        source venv/bin/activate

pip install -r requirements.txt
```

Copiar `env.example` a `.env` y completar, como mínimo, los datos de PostgreSQL
(`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`). Para usar el bot de Discord
completa también `DISCORD_TOKEN` y los canales.

La primera ejecución descarga el modelo de embeddings (`BAAI/bge-m3`, un modelo pesado), por
lo que necesita conexión a internet y espacio en disco.

## Contexto y datos

Proyecto desarrollado inicialmente en el marco de una Práctica Profesional Supervisada en la
UTN FRBA (materia Diseño de Sistemas), con tutoría de docentes. Se desarrolló y evaluó con
conversaciones reales de un curso, que se manejaron únicamente en un entorno local.
**Por privacidad, este repositorio no incluye esos datos**: se reemplazaron por datos
inventados.

- `datos_ejemplo/chat.json`: 45 mensajes ficticios con casos típicos y casos difíciles.
- `config_ejemplo/yaml/`: lista de docentes ficticia y frases de configuración.

## Historia del proyecto

El proyecto tuvo dos etapas.

**Durante la práctica (marzo – julio de 2025, con tutoría docente).**
Una primera versión que ya funcionaba de punta a punta en la parte offline:

- Procesamiento del historial JSON y detección de preguntas y respuestas.
- Base de datos relacional (PostgreSQL) y base vectorial (ChromaDB).
- Búsqueda semántica con embeddings `all-MiniLM-L6-v2`.
- Configuración con `.env` y un sistema de logs para tener trazabilidad: permitía revisar si
  el filtrado y la clasificación de mensajes funcionaban y detectar comportamientos
  anómalos o ajustes pendientes.
- Patrón Strategy, usado solo para distinguir mensajes de alumnos y docentes.

En esa etapa prioricé tener código funcional por sobre el diseño y la mantenibilidad: había
código repetido y acoplado, muchos valores hardcodeados, poco manejo de errores y el
repositorio estaba desordenado.

**Después de la práctica (desarrollo individual).**

- Reorganización del repositorio en módulos (`bot`, `database`, `embeddings`, `processing`,
  `rag`, etc.).
- Bot de Discord, procesamiento en tiempo real y detección de cierres de conversación.
- Generación de respuestas con un modelo local (Ollama) y verificación por oración.
- Migraciones con Alembic y patrón Repository.
- Strategy ampliado (por ejemplo, para los cierres de conversación).
- Cambio del modelo de embeddings a `BAAI/bge-m3`.
- Manejo de errores más sistemático.
- Reducción de código repetido y de acoplamiento.
- Protección de la privacidad: los datos reales se manejan solo en local y el repositorio
  incluye únicamente datos ficticios.
- Licencia MIT.

## Ejecución

Desde la raíz del proyecto:

```bash
python src/main_offline.py   # procesa el JSON, crea la base y los vectores
python src/main_bot.py       # inicia el bot de Discord
```

Para probar la generación con Ollama, poner en el `.env` `RAG_HABILITADO=true` y dejar el bot
corriendo.

## Estructura

```
config_ejemplo/   configuración de ejemplo (docentes y frases, datos ficticios)
datos_ejemplo/    chat.json de ejemplo (datos ficticios)
migrations/       migraciones de Alembic
src/
  bot/            bot de Discord
  configuracion/  carga de la configuración YAML
  database/       modelos, carga y acceso a PostgreSQL
  embeddings/     modelo de embeddings y base vectorial (ChromaDB)
  processing/     detección de preguntas y respuestas (lote y tiempo real)
  rag/            generación y verificación de respuestas
  utils/          rutas, logs y utilidades
```

## Privacidad

Este repositorio **no incluye** datos reales: ni historiales de chat, ni usernames de personas,
ni la configuración real del curso. Si lo usas con conversaciones de personas reales:

- Obtén la autorización de quienes administran el servidor y avisa a los participantes.
- Guarda tu configuración real fuera del repositorio (`CONFIG_DIR` acepta una ruta absoluta).
- Las carpetas `json/`, `logs/` y `chroma/`, y el archivo `.env`, están en `.gitignore`.
  No las subas.
- Los logs pueden contener texto de mensajes. Revísalos antes de compartirlos.

## Pruebas realizadas

Probado manualmente en un servidor de Discord de pruebas, con Ollama (`qwen2.5:7b`):

- Consulta cubierta por conversaciones anteriores: responde con lo que dijo un docente.
- Consulta sin información relacionada: responde que no encontró nada, sin inventar.
- Ollama apagado: pasa a un modo degradado y muestra frases de docentes con un aviso claro.
- Aprendizaje en tiempo real: una pregunta, la respuesta de un docente y el cierre del alumno
  se guardan en la base y el bot las usa en consultas posteriores.

## Limitaciones conocidas

- Los logs guardan en nivel DEBUG el texto de los mensajes y el autor.
- Con `RAG_HABILITADO=false`, el mensaje de respaldo muestra el nombre de usuario de quien
  respondió originalmente.
- Las preguntas abiertas en tiempo real se pierden si el bot se reinicia.
- La detección de preguntas y cierres usa ciertas reglas, por lo que puede cometer errores.
- La verificación de las respuestas es léxica (coincidencia de palabras), no semántica.
- El modelo puede reordenar frases o agregar conectores sin cambiar las palabras, y la
  verificación léxica no lo detecta.

## Próximos pasos

**Código**

- Tests automáticos.
- Mover umbrales y valores hardcodeados a configuración.
- Revisar qué columnas de las tablas son realmente necesarias.

**Datos y análisis**

- Análisis Exploratorio de Datos (EDA).

**Documentación**

- Requerimientos funcionales.
- Diagrama de entidad-relación y diagrama de clases.
- Glosario.
- Documento de decisiones de diseño.

## Licencia

Distribuido bajo licencia MIT. Ver el archivo [LICENSE](LICENSE).
