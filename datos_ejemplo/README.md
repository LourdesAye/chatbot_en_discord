# Dataset de ejemplo (100 % inventado)

`chat.json` tiene 45 mensajes **inventados**: no hay personas, usernames ni conversaciones reales.
Incluye casos difíciles a propósito (preguntas en varios mensajes, dos alumnos preguntando a la vez,
una pregunta administrativa, una respuesta docente con pregunta retórica, un aviso general que
queda como respuesta de una pregunta sin contestar, dos preguntas seguidas del mismo alumno).
Sirve para ver *qué tipo* de errores comete el sistema, no para medir *cuántos*.

Formato: lista de objetos con `id`, `author`, `content`, `timestamp` (ISO 8601) y `attachments`.

## Cómo correrlo (con base, vectores y logs separados de los reales)

En el `.env`:

```
CONFIG_DIR=config_ejemplo
JSON_DIR=datos_ejemplo
DB_NAME=chatbot_demo
CHROMA_DIR=chroma_demo
LOG_DIR=logs_demo
```

Desde la raíz del proyecto:

```
python src/main_offline.py
```
