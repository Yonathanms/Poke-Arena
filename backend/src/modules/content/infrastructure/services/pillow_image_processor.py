import io

from PIL import Image, ImageOps, UnidentifiedImageError

from src.modules.content.application.ports import IImageProcessorPort
from src.modules.content.domain.exceptions import (
    InvalidCardImageError,
    InvalidImageAspectRatioError,
)
from src.modules.content.domain.value_objects import (
    CardImageFormat,
    CardImageMetadata,
    CardThumbnailMetadata,
)


class PillowImageProcessor(IImageProcessorPort):
    """Implementación de procesamiento y validación de proporciones de imágenes con Pillow."""

    CARD_TARGET_RATIO = 5 / 7  # ~0.714
    LOCATION_TARGET_RATIO = 4 / 3  # ~1.333
    TOLERANCE = 0.05
    MIN_CARD_WIDTH = 300
    MIN_CARD_HEIGHT = 420

    @classmethod
    def _is_valid_card_size(cls, width: int, height: int) -> bool:
        target_ratio = 5 / 7
        return (
            width >= cls.MIN_CARD_WIDTH
            and height >= cls.MIN_CARD_HEIGHT
            and abs((width / height) / target_ratio - 1) <= cls.TOLERANCE
        )

    def inspect_card_image(self, raw_bytes: bytes) -> CardImageMetadata:
        """Valida el original sin modificarlo; el binario original queda preservado."""
        if not raw_bytes or len(raw_bytes) > 5_000_000:
            raise InvalidCardImageError()
        try:
            with Image.open(io.BytesIO(raw_bytes)) as image:
                source_format = image.format
                if source_format not in {"PNG", "JPEG", "WEBP"}:
                    raise InvalidCardImageError()
                width = 0
                height = 0
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    image.load()
                    oriented = ImageOps.exif_transpose(image.copy())
                    width, height = oriented.size
                    if not self._is_valid_card_size(width, height):
                        raise InvalidCardImageError()
                return CardImageMetadata(
                    image_format=CardImageFormat(source_format),
                    byte_size=len(raw_bytes),
                    width=width,
                    height=height,
                )
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            if isinstance(exc, InvalidCardImageError):
                raise
            raise InvalidCardImageError() from exc

    def validate_and_process_card_image(self, raw_bytes: bytes) -> tuple[bytes, bytes]:
        """
        Valida que la imagen de carta cumpla proporción 5:7 (tolerancia 5%)
        y genera versión WebP estándar y miniatura.
        """
        image = Image.open(io.BytesIO(raw_bytes))
        width, height = image.size
        actual_ratio = width / height

        if abs(actual_ratio - self.CARD_TARGET_RATIO) > self.TOLERANCE:
            raise InvalidImageAspectRatioError(
                resource_type="carta",
                expected_ratio="5:7",
                actual_ratio=f"{width}:{height} ({actual_ratio:.2f})",
            )

        processed = self._optimize_image(image, max_width=800)
        thumbnail = self._optimize_image(image, max_width=250)
        return processed, thumbnail

    def make_card_thumbnail(
        self, raw_bytes: bytes
    ) -> tuple[bytes, CardThumbnailMetadata]:
        """Produce una miniatura exacta 200×280; el original no se modifica."""
        if not raw_bytes:
            raise InvalidCardImageError()
        try:
            with Image.open(io.BytesIO(raw_bytes)) as source:
                source.seek(0)
                source.load()
                image = ImageOps.exif_transpose(source.copy())
                if not self._is_valid_card_size(image.width, image.height):
                    raise InvalidCardImageError()
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")
                image = self._crop_to_card_ratio(image)
                thumbnail = image.resize((200, 280), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                thumbnail.save(output, format="WEBP", quality=85, method=6)
                content = output.getvalue()
                metadata = CardThumbnailMetadata(
                    image_format=CardImageFormat.WEBP,
                    byte_size=len(content),
                    width=200,
                    height=280,
                )
                return content, metadata
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            if isinstance(exc, InvalidCardImageError):
                raise
            raise InvalidCardImageError() from exc

    @staticmethod
    def _crop_to_card_ratio(image: Image.Image) -> Image.Image:
        """Center-crop a tolerated aspect ratio without distorting the source."""
        target_ratio = 5 / 7
        actual_ratio = image.width / image.height
        if actual_ratio > target_ratio:
            crop_width = int(image.height * target_ratio)
            left = (image.width - crop_width) // 2
            return image.crop((left, 0, left + crop_width, image.height))
        crop_height = int(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        return image.crop((0, top, image.width, top + crop_height))

    def validate_and_process_location_image(self, raw_bytes: bytes) -> tuple[bytes, bytes]:
        """
        Valida que la imagen de ubicación cumpla proporción 4:3 (tolerancia 5%)
        y genera versión WebP estándar y miniatura.
        """
        image = Image.open(io.BytesIO(raw_bytes))
        width, height = image.size
        actual_ratio = width / height

        if abs(actual_ratio - self.LOCATION_TARGET_RATIO) > self.TOLERANCE:
            raise InvalidImageAspectRatioError(
                resource_type="ubicación",
                expected_ratio="4:3",
                actual_ratio=f"{width}:{height} ({actual_ratio:.2f})",
            )

        processed = self._optimize_image(image, max_width=1024)
        thumbnail = self._optimize_image(image, max_width=320)
        return processed, thumbnail

    def _optimize_image(self, image: Image.Image, max_width: int) -> bytes:
        img_copy = image.copy()
        if img_copy.mode in ("RGBA", "P"):
            img_copy = img_copy.convert("RGB")

        if img_copy.width > max_width:
            aspect = img_copy.height / img_copy.width
            new_height = int(max_width * aspect)
            img_copy = img_copy.resize((max_width, new_height), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img_copy.save(output, format="WEBP", quality=85, method=6)
        return output.getvalue()
