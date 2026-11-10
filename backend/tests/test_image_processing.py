"""Pruebas de Pillow sin motores ni credenciales."""

import struct
import zlib
from dataclasses import replace
from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from src.modules.catalogo import catalogo_module as catalogo

ImagenInvalida = catalogo.puertos_imagenes.ImagenInvalida
ContenidoInconsistente = catalogo.puertos_imagenes.ContenidoInconsistente


def binario_imagen(
    formato: str = "PNG",
    size: tuple[int, int] = (600, 840),
    *,
    alpha: bool = False,
    orientation: int | None = None,
) -> bytes:
    """Genera una imagen de prueba reproducible en memoria."""
    salida = BytesIO()
    modo = "RGBA" if alpha else "RGB"
    color = (20, 80, 140, 80) if alpha else (20, 80, 140)
    with Image.new(modo, size, color) as imagen:
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            imagen.save(salida, formato, exif=exif)
        else:
            imagen.save(salida, formato)
    return salida.getvalue()


def _chunk(tipo: bytes, datos: bytes) -> bytes:
    """Codifica un chunk PNG con longitud y CRC correctos."""
    return (
        struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))
    )


@pytest.mark.parametrize("formato", ["PNG", "JPEG", "WEBP"])
def test_procesa_original_y_miniatura(formato: str) -> None:
    """Detecta formatos reales y devuelve original intacto y WebP verificable."""
    original = binario_imagen(formato)
    procesador = catalogo.crear_procesador_imagenes()
    resultado = procesador.procesar(original)
    assert resultado.original.datos == original
    assert resultado.original.metadatos.formato == formato
    assert resultado.original.metadatos.tamano == len(original)
    with Image.open(BytesIO(resultado.miniatura.datos)) as miniatura:
        miniatura.load()
        assert miniatura.format == "WEBP" and miniatura.size == (200, 280)
        pixel: Any = miniatura.getpixel((100, 140))
        assert all(abs(a - b) < 8 for a, b in zip(pixel, (20, 80, 140), strict=True))
    procesador.verificar(resultado)


@pytest.mark.parametrize(
    "formato,size", [("PNG", (300, 420)), ("PNG", (601, 840)), ("GIF", (600, 840))]
)
def test_rechaza_formatos_y_dimensiones_invalidos(formato: str, size: tuple[int, int]) -> None:
    """La proporción y el mínimo se validan independientemente del formato."""
    with pytest.raises(ImagenInvalida):
        catalogo.crear_procesador_imagenes().procesar(binario_imagen(formato, size))


@pytest.mark.parametrize("datos", [b"", b"no es una imagen"])
def test_rechaza_vacio_y_corrupcion(datos: bytes) -> None:
    """Un binario ilegible se clasifica como entrada inválida."""
    with pytest.raises(ImagenInvalida):
        catalogo.crear_procesador_imagenes().procesar(datos)


def test_rechaza_truncamiento_y_cabecera_extrema() -> None:
    """Detecta un JPEG truncado y acota píxeles antes de cargar un PNG."""
    procesador = catalogo.crear_procesador_imagenes()
    png = binario_imagen()
    ihdr = struct.pack(">II", 6000, 8400) + png[24:29]
    grande = png[:8] + _chunk(b"IHDR", ihdr) + png[33:]
    with pytest.raises(ImagenInvalida, match="Dimensiones excesivas"):
        procesador.procesar(grande)
    jpeg = binario_imagen("JPEG")
    with pytest.raises(ImagenInvalida):
        procesador.procesar(jpeg[:-32])


def png_en_limite() -> bytes:
    """Devuelve un PNG válido de 5 000 000 bytes con un chunk auxiliar."""
    png = binario_imagen()
    relleno = _chunk(b"paDd", bytes(5_000_000 - len(png) - 12))
    return png[:-12] + relleno + png[-12:]


def test_limite_decimal_inclusivo() -> None:
    """Acepta exactamente 5 000 000 bytes y rechaza el byte siguiente."""
    exacto = png_en_limite()
    procesador = catalogo.crear_procesador_imagenes()
    assert procesador.procesar(exacto).original.metadatos.tamano == 5_000_000
    with pytest.raises(ImagenInvalida, match="5 000 000"):
        procesador.procesar(exacto + b"x")


@pytest.mark.parametrize("formato", ["PNG", "WEBP"])
def test_rechaza_imagen_animada(formato: str) -> None:
    """Las entradas multiframe se rechazan antes de generar una miniatura."""
    salida = BytesIO()
    with Image.new("RGB", (600, 840), "red") as primera:
        with Image.new("RGB", (600, 840), "blue") as segunda:
            primera.save(salida, formato, save_all=True, append_images=[segunda], duration=100)
    with pytest.raises(ImagenInvalida, match="múltiples cuadros"):
        catalogo.crear_procesador_imagenes().procesar(salida.getvalue())


def test_exif_cambia_dimensiones_visuales_y_se_elimina_de_la_miniatura() -> None:
    """Normaliza EXIF antes de validar 5:7, conservando los bytes de entrada."""
    original = binario_imagen("JPEG", (840, 600), orientation=6)
    procesador = catalogo.crear_procesador_imagenes()
    resultado = procesador.procesar(original)
    assert resultado.original.datos == original
    assert (resultado.original.metadatos.ancho, resultado.original.metadatos.alto) == (600, 840)
    with Image.open(BytesIO(resultado.miniatura.datos)) as miniatura:
        assert miniatura.size == (200, 280)
        assert 274 not in miniatura.getexif()
    procesador.verificar(resultado)


def test_preserva_transparencia() -> None:
    """El canal alfa se conserva al convertir PNG a WebP."""
    resultado = catalogo.crear_procesador_imagenes().procesar(binario_imagen(alpha=True))
    with Image.open(BytesIO(resultado.miniatura.datos)) as miniatura:
        assert miniatura.mode == "RGBA"
        assert miniatura.getchannel("A").getextrema() == (80, 80)


def test_verificacion_detecta_hash_y_metadatos_inconsistentes() -> None:
    """Los bytes deben coincidir con el hash SQL y los metadatos de ambos archivos."""
    procesador = catalogo.crear_procesador_imagenes()
    imagen = procesador.procesar(binario_imagen())
    for campo, cambios in (("original", {"sha256": "0" * 64}), ("miniatura", {"tamano": 1})):
        archivo = getattr(imagen, campo)
        alterado = replace(archivo, metadatos=replace(archivo.metadatos, **cambios))
        with pytest.raises(ContenidoInconsistente):
            procesador.verificar(replace(imagen, **{campo: alterado}))


def test_fallo_del_codificador_se_traduce(monkeypatch: pytest.MonkeyPatch) -> None:
    """El fallo al generar la miniatura es distinto de una entrada inválida."""
    original = binario_imagen()

    def fallar(*args: Any, **kwargs: Any) -> None:
        raise OSError("detalle privado del codificador")

    monkeypatch.setattr(Image.Image, "save", fallar)
    with pytest.raises(catalogo.puertos_imagenes.ErrorProcesamiento) as exc:
        catalogo.crear_procesador_imagenes().procesar(original)
    assert "privado" not in str(exc.value)
