import io

import pytest
from PIL import Image

from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import (
    InvalidCardCostError,
    InvalidCardPowerError,
    InvalidImageAspectRatioError,
)
from src.modules.content.domain.value_objects import (
    CardRarity,
    CardType,
)
from src.modules.content.infrastructure.services.pillow_image_processor import (
    PillowImageProcessor,
)


def create_test_image_bytes(width: int, height: int) -> bytes:
    """Helper para generar imágenes en memoria con dimensiones específicas."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestCardDomain:
    def test_create_valid_card(self) -> None:
        card = Card.create(
            code="PKA-FUE-001",
            name="Charmander",
            cost=2,
            power=3,
            card_type=CardType.FUEGO,
            rarity=CardRarity.COMUN,
            image_url="/uploads/cards/charmander.webp",
        )
        assert card.code == "PKA-FUE-001"
        assert card.cost == 2
        assert card.power == 3
        assert card.card_type == CardType.FUEGO

    def test_card_cost_below_one_raises_error(self) -> None:
        with pytest.raises(InvalidCardCostError):
            Card.create(
                code="PKA-FUE-002",
                name="Magikarp",
                cost=0,
                power=1,
                card_type=CardType.AGUA,
                rarity=CardRarity.COMUN,
                image_url="/uploads/cards/magikarp.webp",
            )

    def test_card_cost_above_six_raises_error(self) -> None:
        with pytest.raises(InvalidCardCostError):
            Card.create(
                code="PKA-FUE-003",
                name="Charizard",
                cost=7,
                power=10,
                card_type=CardType.FUEGO,
                rarity=CardRarity.EPICA,
                image_url="/uploads/cards/charizard.webp",
            )

    def test_card_negative_power_raises_error(self) -> None:
        with pytest.raises(InvalidCardPowerError):
            Card.create(
                code="PKA-FUE-004",
                name="Weakling",
                cost=1,
                power=-1,
                card_type=CardType.INCOLORO,
                rarity=CardRarity.COMUN,
                image_url="/uploads/cards/weak.webp",
            )


class TestImageProcessor:
    def test_valid_card_aspect_ratio_5_7(self) -> None:
        processor = PillowImageProcessor()
        # 500 x 700 tiene proporción exacta 5:7
        img_bytes = create_test_image_bytes(500, 700)
        proc, thumb = processor.validate_and_process_card_image(img_bytes)
        assert len(proc) > 0
        assert len(thumb) > 0

    def test_invalid_card_aspect_ratio_raises_error(self) -> None:
        processor = PillowImageProcessor()
        # 500 x 500 es cuadrado (1:1), debe fallar
        img_bytes = create_test_image_bytes(500, 500)
        with pytest.raises(InvalidImageAspectRatioError):
            processor.validate_and_process_card_image(img_bytes)

    def test_valid_location_aspect_ratio_4_3(self) -> None:
        processor = PillowImageProcessor()
        # 800 x 600 tiene proporción exacta 4:3
        img_bytes = create_test_image_bytes(800, 600)
        proc, thumb = processor.validate_and_process_location_image(img_bytes)
        assert len(proc) > 0
        assert len(thumb) > 0

    def test_invalid_location_aspect_ratio_raises_error(self) -> None:
        processor = PillowImageProcessor()
        # 500 x 700 es 5:7, no 4:3, debe fallar para ubicación
        img_bytes = create_test_image_bytes(500, 700)
        with pytest.raises(InvalidImageAspectRatioError):
            processor.validate_and_process_location_image(img_bytes)
