"""Creación centralizada del modelo de embeddings (se elige con EMBEDDINGS_MODELO en el .env)."""
import os

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

# Modelo multilingüe liviano (entiende español); reemplaza a all-MiniLM-L6-v2, pensado para inglés.
MODELO_EMBEDDINGS_POR_DEFECTO = "paraphrase-multilingual-MiniLM-L12-v2"


def nombre_modelo_embeddings() -> str:
    load_dotenv()
    return (os.getenv("EMBEDDINGS_MODELO") or MODELO_EMBEDDINGS_POR_DEFECTO).strip()


def crear_modelo_embeddings(nombre: str | None = None) -> HuggingFaceEmbeddings:
    """Crea el modelo con los vectores normalizados.

    La normalización es imprescindible: la búsqueda calcula la similitud como 1 - (distancia L2)²,
    que solo tiene sentido (valores entre -1 y 1) si los vectores tienen largo 1. Algunos modelos
    (por ejemplo los `paraphrase-*`) no los normalizan por defecto.
    """
    return HuggingFaceEmbeddings(
        model_name=nombre or nombre_modelo_embeddings(),
        encode_kwargs={"normalize_embeddings": True},
    )
