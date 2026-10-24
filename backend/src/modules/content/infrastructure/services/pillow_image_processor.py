import io

from PIL import Image

from src.modules.content.application.ports import IImageProcessorPort
from src.modules.content.domain.exceptions import InvalidImageAspectRatioError


class PillowImageProcessor(IImageProcessorPort):
    """Implementación de procesamiento y validación de proporciones de imágenes con Pillow."""

    CARD_TARGET_RATIO = 5 / 7  # ~0.714
    LOCATION_TARGET_RATIO = 4 / 3  # ~1.333
    TOLERANCE = 0.05

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
