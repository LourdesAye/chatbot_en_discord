from database.models.clase_mensajes import Mensaje
from database.models.clase_preguntas import Pregunta


class EstrategiaCierre:
    def cerrar(self, pregunta: Pregunta, mensaje: Mensaje, motivo: str):
        raise NotImplementedError("Debes implementar el método cerrar")


class EstrategiaCierreBatch(EstrategiaCierre):
    """Marca la pregunta como cerrada y delega el registro al procesador.

    Se usa tanto en el procesamiento por lotes como en tiempo real: en tiempo real
    el procesador extiende `registrar_cierre` para persistir e indexar la pregunta.
    """

    def __init__(self, procesador):
        self.procesador = procesador

    def cerrar(self, pregunta: Pregunta, mensaje: Mensaje, motivo: str):
        pregunta.cerrar()
        self.procesador.registrar_cierre(pregunta, motivo)
