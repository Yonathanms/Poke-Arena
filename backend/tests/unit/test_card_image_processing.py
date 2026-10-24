"""Stage 5 image processing invariants."""

import io

import pytest
from PIL import Image

from src.modules.content.domain.value_objects import CardImageFormat
from src.modules.content.infrastructure.services.pillow_image_processor import PillowImageProcessor


def _image_bytes(image: Image.Image, image_format: str, **kwargs: object) -> bytes:
    output = io.BytesIO()
    image.save(output, format=image_format, **kwargs)
    return output.getvalue()


def test_card_thumbnail_is_exact_webp_200_by_280() -> None:
    source = Image.new("RGB", (600, 840), "red")
    raw = _image_bytes(source, "PNG")

    thumbnail, metadata = PillowImageProcessor().make_card_thumbnail(raw)

    with Image.open(io.BytesIO(thumbnail)) as result:
        assert result.format == "WEBP"
        assert result.size == (200, 280)
    assert metadata.image_format is CardImageFormat.WEBP
    assert metadata.width == 200
    assert metadata.height == 280


def test_inspector_and_thumbnail_apply_exif_orientation() -> None:
    # Stored raster is landscape; orientation 6 presents a valid 5:7 portrait.
    source = Image.new("RGB", (840, 600), "blue")
    exif = Image.Exif()
    exif[274] = 6
    raw = _image_bytes(source, "JPEG", exif=exif)
    processor = PillowImageProcessor()

    metadata = processor.inspect_card_image(raw)
    thumbnail, thumbnail_metadata = processor.make_card_thumbnail(raw)

    assert (metadata.width, metadata.height) == (600, 840)
    assert (thumbnail_metadata.width, thumbnail_metadata.height) == (200, 280)
    with Image.open(io.BytesIO(thumbnail)) as result:
        assert result.size == (200, 280)


def test_animated_webp_is_inspected_but_thumbnail_uses_first_frame() -> None:
    first = Image.new("RGB", (600, 840), "red")
    second = Image.new("RGB", (600, 840), "green")
    raw = _image_bytes(first, "WEBP", save_all=True, append_images=[second], duration=100)
    processor = PillowImageProcessor()

    metadata = processor.inspect_card_image(raw)
    thumbnail, _ = processor.make_card_thumbnail(raw)

    assert metadata.image_format is CardImageFormat.WEBP
    with Image.open(io.BytesIO(thumbnail)) as result:
        assert result.getpixel((100, 140))[0] > result.getpixel((100, 140))[1]


@pytest.mark.parametrize("size", [(601, 840), (600, 839)])
def test_inspector_rejects_non_exact_ratio_or_below_minimum(size: tuple[int, int]) -> None:
    from src.modules.content.domain.exceptions import InvalidCardImageError

    raw = _image_bytes(Image.new("RGB", size), "PNG")
    with pytest.raises(InvalidCardImageError):
        PillowImageProcessor().inspect_card_image(raw)
