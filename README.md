# Chatbot de consultas para Discord (RAG con modelo local)

Bot de Discord que responde consultas de estudiantes usando conversaciones previas entre
alumnos y docentes de un curso. Procesa historiales exportados en JSON, guarda las preguntas
y respuestas en PostgreSQL, las indexa con embeddings en ChromaDB y genera la respuesta con un
modelo local (Ollama), verificando que cada oración esté apoyada en lo que dijo un docente.

## Cómo funciona

1. **Procesamiento**: se leen los mensajes del JSON, se detectan preguntas, respuestas de
   docentes y cierres de conversación.
2. **Base de datos**: las preguntas con respuesta de un docente se guardan en PostgreSQL
   (esquema gestionado con Alembic).
3. **Embeddings**: cada pregunta se indexa en ChromaDB.
4. **RAG**: ante una consulta nueva se buscan las preguntas más parecidas, se arma un contexto
   con las respuestas de docentes y un modelo local de Ollama redacta la respuesta. El código
   descarta las oraciones que no estén respaldadas por los fragmentos recuperados.
5. **Bot de Discord**: responde en un hilo y puede seguir aprendiendo en tiempo real de
   canales donde alumnos preguntan y docentes responden.

## Requisitos

- Python 3.11
- PostgreSQL
- [Ollama](https://ollama.com) con un modelo descargado (por ejemplo `ollama pull qwen2.5:3b`).
  Es opcional: con `RAG_HABILITADO=false` no se usa.
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

La primera ejecución descarga el modelo de embeddings, por lo que necesita conexión a internet.

## Sobre los datos

El repositorio incluye únicamente datos **inventados**:

- `datos_ejemplo/chat.json`: 45 mensajes ficticios con casos típicos y casos difíciles.
- `config_ejemplo/yaml/`: lista de docentes ficticia y frases de configuración.

## Ejecución 

Desde la raíz del proyecto:

```bash
python src/main_offline.py   # procesa el JSON, crea la base y los vectores
python src/main_bot.py       # inicia el bot de Discord
```

Para probar la generación con Ollama, poner en el .env `RAG_HABILITADO=true` y dejar el bot corriendo. 

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

## Limitaciones conocidas

- Los logs guardan en nivel DEBUG el texto de los mensajes y el autor.
- Con `RAG_HABILITADO=false`, el mensaje de respaldo muestra el nombre de usuario de quien
  respondió originalmente.
- Las preguntas abiertas en tiempo real se pierden si el bot se reinicia.
- La detección de preguntas y cierres usa ciertas reglas, por lo que puede cometer errores.
- La verificación de las respuestas es léxica (coincidencia de palabras), no semántica.

## Próximos pasos
- Tests automáticos.
- Análisis Exploratorio de Datos (EDA).
- Mover los umbrales fijos o hardcodeados a un archivo de configuración.
- Incorporación de documentación
  - Glosario
  - Diagrama de Clases
  - Documento de Decisiones de Diseño
