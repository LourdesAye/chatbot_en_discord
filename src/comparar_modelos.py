"""Compara modelos de embeddings con tus preguntas reales.

Solo LEE de PostgreSQL: no modifica `chroma/` ni la base. Sirve para:
  - ver cuánto tarda cada modelo y cuánto "separa" lo que es del tema de lo que no,
  - elegir el umbral RAG_UMBRAL_SIMILITUD (usa la misma escala que el bot).

Uso (desde la raíz del proyecto):
    python src/comparar_modelos.py                       # usa el modelo de EMBEDDINGS_MODELO (.env)
    python src/comparar_modelos.py all-MiniLM-L6-v2 BAAI/bge-m3   # compara varios modelos

Qué es automático y qué es manual:
  - Las preguntas de tu base (las que el chatbot puede encontrar) se cargan SOLAS desde PostgreSQL.
  - Las consultas de prueba las escribís VOS en `consultas_calibracion.txt` (raíz del proyecto), una por línea:
        + consulta del tema   (tu base SÍ tiene información sobre eso)
        - consulta fuera de tema (tu base NO tiene nada parecido)
    Escribilas como las escribiría un alumno; NO copies una pregunta exacta de la base (daría similitud
    casi perfecta y no mostraría cómo se comporta el bot con consultas reales).

Verificación: con all-MiniLM-L6-v2 las similitudes deberían coincidir con las líneas "Similitud:" del
log del bot (logs_generacion_embeddings.txt) para la misma consulta.
"""
import os
import sys
import time

import numpy as np

from embeddings.extraer_preguntas import obtener_preguntas_y_metadatos
from embeddings.modelo_embeddings import crear_modelo_embeddings, nombre_modelo_embeddings

# Consultas de respaldo: solo se usan si no existe consultas_calibracion.txt (o no tiene líneas + / -)
CONSULTAS_DEL_TEMA = [
    "hola bot, cómo andas? para qué sirve el patrón state? gracias!",
    "¿Para qué sirve el patrón State?",
]
CONSULTAS_FUERA_DE_TEMA = [
    "hola, tengo una duda? como esta el clima en buenos aires?",
    "¿Cuál es la receta de las milanesas?",
]

ARCHIVO_CONSULTAS = "consultas_calibracion.txt"


def cargar_consultas():
    """Lee el archivo de consultas y devuelve dos listas: (del tema, fuera de tema)."""
    if not os.path.exists(ARCHIVO_CONSULTAS):
        return CONSULTAS_DEL_TEMA, CONSULTAS_FUERA_DE_TEMA

    tema, fuera = [], []                       # dos listas vacías donde se van juntando las consultas
    with open(ARCHIVO_CONSULTAS, encoding="utf-8") as f:
        for linea in f:                        # recorre el archivo renglón por renglón
            linea = linea.strip()              # quita espacios y saltos de línea de los extremos
            if linea.startswith("+"):          # ¿el renglón empieza con "+"? -> consulta del tema
                # linea[1:] = el texto SIN el primer carácter (el "+"). .strip() quita el espacio que sobra.
                # .append(...) agrega ese texto al final de la lista.
                # Ejemplo: "+ hola bot"  ->  linea[1:] = " hola bot"  ->  .strip() = "hola bot"
                tema.append(linea[1:].strip())
            elif linea.startswith("-"):        # empieza con "-" -> consulta fuera de tema
                fuera.append(linea[1:].strip())
            # los renglones que empiezan con "#" o están vacíos no entran en ningún if: se ignoran
    print(f"Consultas leídas de {ARCHIVO_CONSULTAS}: {len(tema)} del tema, {len(fuera)} fuera de tema")
    # "tema or X": si la lista quedó vacía (no hay renglones con "+"), usa la lista de respaldo X
    return tema or CONSULTAS_DEL_TEMA, fuera or CONSULTAS_FUERA_DE_TEMA


def similitudes(modelo, vectores, consulta):
    """Similitud de UNA consulta con TODAS las preguntas de la base. Devuelve un número por pregunta.

    Misma escala que el bot: 1 - (distancia L2)² = 2·coseno - 1 (vectores normalizados).
    """
    # embed_query: convierte UN texto (la consulta) en un vector, o sea una lista de números
    q = np.array(modelo.embed_query(consulta))
    # `vectores` tiene una fila por pregunta de la base. `vectores @ q` multiplica cada fila por q
    # (producto escalar) y da, para cada pregunta, qué tan parecida es a la consulta (coseno, de -1 a 1).
    # Luego 2*x - 1 lo pasa a la escala que usa el bot en sus logs.
    return 2 * (vectores @ q) - 1


def evaluar(nombre, textos, del_tema, fuera_de_tema):
    print(f"\n{'=' * 78}\nMODELO: {nombre}")

    # --- 1) cargar el modelo y medir cuánto tarda ---
    t0 = time.perf_counter()                   # reloj: guarda la hora de inicio
    modelo = crear_modelo_embeddings(nombre)
    # "Calentamiento": la primera vez que un modelo procesa un texto suele tardar más (preparaciones
    # internas). Se hace una pasada con una palabra cualquiera ("calentamiento" no significa nada
    # especial) para que ese costo de arranque no se cuente en las mediciones siguientes.
    modelo.embed_query("calentamiento")
    print(f"  carga del modelo:        {time.perf_counter() - t0:6.1f} s")

    # --- 2) convertir TODAS las preguntas de la base en vectores ---
    t0 = time.perf_counter()
    # embed_documents: igual que embed_query pero recibe una LISTA de textos y devuelve una lista de
    # vectores (uno por texto). Es más eficiente que llamar a embed_query en un bucle.
    vectores = np.array(modelo.embed_documents(textos))   # tabla: una fila por pregunta
    print(f"  indexar {len(textos)} preguntas:   {time.perf_counter() - t0:6.1f} s  (vectores de {vectores.shape[1]} dimensiones)")

    # --- 3) probar cada consulta y guardar su MEJOR similitud ---
    mejores = {"tema": [], "fuera": []}        # diccionario con dos listas, una por tipo de consulta
    for etiqueta, consultas in (("tema", del_tema), ("fuera", fuera_de_tema)):
        for consulta in consultas:
            t0 = time.perf_counter()
            sims = similitudes(modelo, vectores, consulta)    # un número por cada pregunta de la base
            ms = (time.perf_counter() - t0) * 1000
            # np.argsort(x) devuelve las POSICIONES que ordenarían x de menor a mayor.
            # Con el signo menos (-sims) el orden se invierte: primero las posiciones de las MAYORES
            # similitudes. [:3] se queda con las 3 primeras = las 3 preguntas más parecidas.
            # Ejemplo: sims = [0.1, 0.9, 0.4]  ->  argsort(-sims) = [1, 2, 0]  ->  [:3] = [1, 2, 0]
            top = np.argsort(-sims)[:3]
            print(f"\n  [{'DEL TEMA' if etiqueta == 'tema' else 'FUERA DE TEMA'}] {consulta}   ({ms:.0f} ms)")
            for i in top:
                print(f"     {sims[i]:7.3f}  {textos[i][:85]!r}")    # similitud y primeros 85 caracteres
            mejores[etiqueta].append(float(sims[top[0]]))   # top[0] = la pregunta MÁS parecida

    # --- 4) resumen y umbral sugerido ---
    peor_del_tema = min(mejores["tema"]) if mejores["tema"] else None     # la más baja entre las "del tema"
    mejor_fuera = max(mejores["fuera"]) if mejores["fuera"] else None     # la más alta entre las "fuera de tema"
    print("\n  RESUMEN")
    print(f"     peor similitud entre las consultas del tema:       {peor_del_tema}")
    print(f"     mejor similitud entre las consultas fuera de tema:  {mejor_fuera}")
    if peor_del_tema is not None and mejor_fuera is not None:
        if peor_del_tema > mejor_fuera:
            # hay un "hueco" entre ambos grupos: el umbral sugerido es el punto medio
            print(f"     ✅ Se separan. RAG_UMBRAL_SIMILITUD sugerido: {max(0.0, (peor_del_tema + mejor_fuera) / 2):.2f}")
        else:
            print("     ⚠️ No se separan con un único umbral: probá otro modelo o agregá más consultas.")


def main():
    # sys.argv es la lista de "palabras" con las que se ejecutó el programa:
    #   python src\comparar_modelos.py all-MiniLM-L6-v2 BAAI/bge-m3
    #   sys.argv = ["src\\comparar_modelos.py", "all-MiniLM-L6-v2", "BAAI/bge-m3"]
    # sys.argv[0] es el nombre del script; sys.argv[1:] son todas las demás = los modelos a comparar.
    # "lista or [X]": si no se escribió ningún modelo (lista vacía), usa el del .env.
    nombres = sys.argv[1:] or [nombre_modelo_embeddings()]
    textos, _ = obtener_preguntas_y_metadatos()     # las preguntas de la base, cargadas solas desde PostgreSQL
    if not textos:
        print("No hay preguntas aptas en la base de datos. Ejecutá antes main_offline.py")
        return
    print(f"Preguntas aptas para el chatbot en la base: {len(textos)}")
    del_tema, fuera_de_tema = cargar_consultas()
    for nombre in nombres:
        evaluar(nombre, textos, del_tema, fuera_de_tema)


if __name__ == "__main__":
    main()
