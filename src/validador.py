from configuracion.repository import Repositorio
from funciones_normalizadoras_de_texto import NormalizadorUsuario


class Validador:
    """Contiene las reglas de validación que utiliza la aplicación. Los datos se obtienen del repositorio una única vez , durante la inicialización."""

    def __init__(self, repositorio: Repositorio):
        """Inicializa el validador y carga los datos necesarios."""

        self._docentes = frozenset(
            NormalizadorUsuario.normalizar(docente)
            for docente in repositorio.obtener_docentes()
        )

        self._frases_administrativas = repositorio.obtener_frases_administrativas()

        self._frases_cierre_alumnos = repositorio.obtener_frases_cierre_alumnos()

        self._frases_cierre_docente = repositorio.obtener_frases_cierre_docentes()

        self._frases_tipicas_de_preguntas = repositorio.obtener_frases_habituales_en_preguntas()

    def es_docente(self, usuario: str) -> bool:
        """ Determina si un usuario de Discord corresponde a un docente.
        La comparación entre usuarios se hace cuando ambos están normalizados. """

        usuario_normalizado = NormalizadorUsuario.normalizar(usuario)

        return usuario_normalizado in self._docentes

    def obtener_docentes(self)-> frozenset[str]:
        """ Obtiene la lista de usuarios de Discord que son docentes """
        return self._docentes


    def obtener_frases_administrativas(self) -> frozenset[str]:
        """ Obtiene las frases administrativas. """
        return self._frases_administrativas

    def obtener_frases_cierre_alumnos(self) -> frozenset[str]:
        """ Obtiene las frases de cierre de alumnos. """
        return self._frases_cierre_alumnos

    def obtener_frases_cierre_docentes(self) -> frozenset[str]:
        """ Obtiene las frases de cierre de docentes configuradas. """
        return self._frases_cierre_docente

    def obtener_frases_tipicas_en_preguntas(self) -> frozenset[str]:
        """ Obtiene las frases clave utilizadas para detectar preguntas. """
        return self._frases_tipicas_de_preguntas
