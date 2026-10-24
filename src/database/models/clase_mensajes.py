import os
import re

import pandas as pd

from database.models.utilidades_modelo_dominio import (
    contar_palabras,
    primeras_cinco_palabras,
)
from validador import Validador

from datetime import datetime
from typing import Iterable


class Mensaje:
    def __init__(
        self,
        id_mensaje: int | str,
        autor: str,
        contenido: str,
        timestamp: datetime | str,
        attachments: Iterable[tuple[str, str]] | None,
        origen: str,
        validador: Validador,
    ):
        self.id_mensaje_base_de_datos: int | None = None

        self.id_mensaje_discord = str(id_mensaje).strip()
        self.autor = autor.strip()
        self.contenido = contenido.strip()
        self.timestamp = timestamp
        self.attachments = list(attachments or [])
        self.origen = origen
        self.validador = validador

    @classmethod
    def convertir_fila_a_mensaje(
        cls,
        fila_df,
        ruta_json: str,
        validador: Validador,
    ) -> "Mensaje":
        return cls(
            id_mensaje=fila_df["id"],
            autor=fila_df["author"],
            contenido=fila_df["content"],
            timestamp=fila_df["timestamp"],
            attachments=cls._procesar_attachments(
                fila_df.get("attachments", [])
            ),
            origen=ruta_json,
            validador=validador,
        )

    @classmethod
    def from_discord(
        cls,
        discord_message,
        validador: Validador,
    ) -> "Mensaje":
        attachments = []

        for attachment in discord_message.attachments:
            filename = attachment.filename
            extension = filename.rsplit(".", 1)[-1] if "." in filename else ""

            attachments.append((filename, extension))

        autor = getattr(
            discord_message.author,
            "name",
            str(discord_message.author),
        )

        return cls(
            id_mensaje=discord_message.id,
            autor=autor,
            contenido=discord_message.content or "",
            timestamp=discord_message.created_at.isoformat(),
            attachments=attachments,
            origen="discord_tiempo_real",
            validador=validador,
        )

    @staticmethod
    def _procesar_attachments(lista_adjuntos):
        return [
            (
                os.path.basename(adjunto),
                os.path.basename(adjunto).rsplit(".", 1)[-1]
                if "." in os.path.basename(adjunto)
                else "",
            )
            for adjunto in lista_adjuntos
        ]

    def contiene_frase_clave(self):
        frases_tipicas_en_preguntas = self.validador.obtener_frases_tipicas_en_preguntas()
        # si dentro en el contenido del mensaje esta la frase exacta incluida tenga mayusculas o minúsculas
        return any( re.search( rf"\b{re.escape(f)}\b", self.contenido, flags=re.IGNORECASE) for f in frases_tipicas_en_preguntas)
        
            
    def contiene_signo_interrogacion(self):
        return "?" in self.contenido or "\u00bf" in self.contenido # ¿ es "\u00bf"

    def es_autor_docente(self) -> bool:
        return self.autor in self.validador.obtener_docentes()

    def es_pregunta(self):
        return self.contiene_signo_interrogacion() or self.contiene_frase_clave()
            

    def es_cierre_alumno(self):
        frases_cierre_alumnos = self.validador.obtener_frases_cierre_alumnos()
        # Analiza si las primeras 5 palabras pueden ser una frase de cierre de alumno
        return contar_palabras(self.contenido) <= 5 and any(f in self.contenido.lower() for f in frases_cierre_alumnos)

    
    def es_cierre_docente(self): 
        frases_cierre_docentes = self.validador.obtener_frases_cierre_docentes()
        # Analiza si el contenido es una frase de cierre (genial, joya, gracias, etc.) por parte del docente
        inicio = primeras_cinco_palabras(self.contenido).lower() # Analiza si las primeras 5 palabras pueden ser una frase de cierre del docente
        return any(f in inicio for f in frases_cierre_docentes)
