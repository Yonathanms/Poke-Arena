"""Puertos y errores de medios independientes de Pillow, MongoDB y SQL."""

from typing import Protocol

from ..domain.imagen_model import ImagenAlmacenada, ImagenProcesada, ReferenciasImagen


class ErrorImagen(Exception):
    """Fallo de medios con un mensaje seguro para el consumidor."""


class ImagenInvalida(ErrorImagen):
    """El original incumple las reglas de entrada y debe reemplazarse."""


class ErrorProcesamiento(ErrorImagen):
    """La transformación o validación de salida no pudo completarse."""


class ArchivoNoExiste(ErrorImagen):
    """No hay un archivo completo para la referencia indicada."""


class ContenidoInconsistente(ErrorImagen):
    """La referencia, el contenido o sus metadatos son incompatibles."""


class ErrorAlmacenamiento(ErrorImagen):
    """Fallo de infraestructura, con indicación de si admite reintento."""

    def __init__(self, *, reintentable: bool) -> None:
        """Mantiene el diagnóstico público separado de la excepción del driver."""
        super().__init__("Falló la operación de almacenamiento de imagen")
        self.reintentable = reintentable


class ErrorGuardadoPar(ErrorImagen):
    """Fallo de guardado con IDs reservados y escrituras completas confirmadas."""

    def __init__(
        self,
        referencias: ReferenciasImagen,
        confirmadas: tuple[str, ...],
        causa: ErrorImagen,
    ) -> None:
        """Los IDs restantes pueden contener una escritura de resultado incierto."""
        super().__init__("No se confirmó el almacenamiento de ambos archivos")
        self.referencias = referencias
        self.confirmadas = confirmadas
        self.causa = causa


class ProcesadorImagenPort(Protocol):
    """Procesamiento local síncrono y verificación de binarios contra metadatos."""

    def procesar(self, original: bytes) -> ImagenProcesada:
        """Valida el original y genera una miniatura WebP decodificable."""
        ...

    def verificar(self, imagen: ImagenProcesada) -> None:
        """Contrasta ambos binarios y lanza ContenidoInconsistente si difieren."""
        ...


class AlmacenImagenPort(Protocol):
    """Almacenamiento de pares bajo propiedad exclusiva del llamador."""

    def reservar(self) -> ReferenciasImagen:
        """Genera IDs sin escribir. Conservarlos antes de guardar o reintentar."""
        ...

    async def guardar_par(
        self,
        referencias: ReferenciasImagen,
        imagen: ImagenProcesada,
    ) -> ImagenAlmacenada:
        """Guarda ambos binarios. Un reintento usa los mismos IDs y bytes."""
        ...

    async def recuperar(self, referencia: str) -> bytes:
        """Recupera un binario completo por ID con un límite de tamaño."""
        ...

    async def verificar_par(self, imagen: ImagenAlmacenada) -> None:
        """Recupera ambos binarios y verifica los metadatos esperados."""
        ...

    async def eliminar(self, referencia: str) -> None:
        """Elimina un ID propio, incluidos fragmentos huérfanos de ese ID."""
        ...
