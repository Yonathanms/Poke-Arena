import io

import pytest
from PIL import Image

from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import (
    AbilityRequiredError,
    CardCodeTypeMismatchError,
    InvalidAbilityCodeError,
    InvalidCardCodeError,
    InvalidCardCostError,
    InvalidCardImageMetadataError,
    InvalidCardPowerError,
    InvalidImageAspectRatioError,
)
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardCode,
    CardImageFormat,
    CardImageMetadata,
    CardImageState,
    CardRarity,
    CardThumbnailMetadata,
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
    @staticmethod
    def create_card(
        *,
        code: str = "PKA-FUE-001",
        name: str = "Charmander",
        cost: int = 2,
        power: int = 3,
        card_type: CardType = CardType.FUEGO,
        rarity: CardRarity = CardRarity.COMUN,
        image_url: str = "/uploads/cards/charmander.png",
        thumbnail_url: str | None = None,
        ability_code: AbilityCode | None = AbilityCode("HAB-000"),
        image_state: CardImageState = CardImageState.PENDING,
        image_metadata: CardImageMetadata | None = None,
        thumbnail_metadata: CardThumbnailMetadata | None = None,
    ) -> Card:
        return Card.create(
            code=code,
            name=name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            ability_code=ability_code,
            image_state=image_state,
            image_metadata=image_metadata,
            thumbnail_metadata=thumbnail_metadata,
        )

    def test_create_valid_card(self) -> None:
        card = self.create_card()
        assert card.code == "PKA-FUE-001"
        assert card.cost == 2
        assert card.power == 3
        assert card.card_type == CardType.FUEGO
        assert card.ability_code == AbilityCode("HAB-000")

    @pytest.mark.parametrize("cost", [0, 7, 10])
    def test_card_cost_inclusive_boundaries_are_valid(self, cost: int) -> None:
        card = self.create_card(cost=cost)
        assert card.cost == cost

    @pytest.mark.parametrize("cost", [-1, 11])
    def test_card_cost_outside_official_range_raises_error(self, cost: int) -> None:
        with pytest.raises(InvalidCardCostError):
            self.create_card(cost=cost)

    @pytest.mark.parametrize("power", [-20, -1, 20])
    def test_card_power_inclusive_boundaries_are_valid(self, power: int) -> None:
        card = self.create_card(power=power)
        assert card.power == power

    @pytest.mark.parametrize("power", [-21, 21])
    def test_card_power_outside_official_range_raises_error(self, power: int) -> None:
        with pytest.raises(InvalidCardPowerError):
            self.create_card(power=power)

    def test_missing_ability_is_rejected_without_defaulting_to_hab_000(self) -> None:
        with pytest.raises(AbilityRequiredError):
            self.create_card(ability_code=None)
        with pytest.raises(AbilityRequiredError):
            Card()

    def test_hab_000_is_a_valid_explicit_ability_selection(self) -> None:
        card = self.create_card(ability_code=AbilityCode("HAB-000"))
        assert card.ability_code == AbilityCode("HAB-000")

    def test_card_code_type_must_match_card_type(self) -> None:
        with pytest.raises(CardCodeTypeMismatchError):
            self.create_card(code="PKA-AGU-001")

    @pytest.mark.parametrize("code", ["PKA-INC-001", "PKA-FUE-000", "PKA-FUE-1000"])
    def test_card_code_must_use_an_official_type_and_sequence(self, code: str) -> None:
        with pytest.raises(InvalidCardCodeError):
            CardCode(code)

    def test_invalid_ability_code_is_rejected(self) -> None:
        with pytest.raises(InvalidAbilityCodeError):
            AbilityCode("SIN-HABILIDAD")

    @staticmethod
    def valid_original_metadata() -> CardImageMetadata:
        return CardImageMetadata(
            image_format=CardImageFormat.PNG,
            byte_size=1_000,
            width=600,
            height=840,
        )

    @staticmethod
    def valid_thumbnail_metadata() -> CardThumbnailMetadata:
        return CardThumbnailMetadata(
            image_format=CardImageFormat.WEBP,
            byte_size=500,
            width=200,
            height=280,
        )

    def test_availability_requires_ready_state_both_references_and_metadata(self) -> None:
        card = self.create_card(
            image_state=CardImageState.READY,
            thumbnail_url="/uploads/cards/thumb.webp",
            image_metadata=self.valid_original_metadata(),
            thumbnail_metadata=self.valid_thumbnail_metadata(),
        )
        assert card.available_to_players is True

    def test_ready_card_without_original_reference_is_not_available(self) -> None:
        card = self.create_card(
            image_url=" ",
            image_state=CardImageState.READY,
            thumbnail_url="/uploads/cards/thumb.webp",
            image_metadata=self.valid_original_metadata(),
            thumbnail_metadata=self.valid_thumbnail_metadata(),
        )
        assert card.available_to_players is False

    @pytest.mark.parametrize(
        "metadata_values",
        [
            {"byte_size": 0, "width": 600, "height": 840},
            {"byte_size": 5_000_001, "width": 600, "height": 840},
            {"byte_size": 1_000, "width": 299, "height": 420},
            {"byte_size": 1_000, "width": 300, "height": 419},
            {"byte_size": 1_000, "width": 300, "height": 500},
        ],
    )
    def test_invalid_original_metadata_is_rejected(
        self, metadata_values: dict[str, int]
    ) -> None:
        with pytest.raises(InvalidCardImageMetadataError):
            CardImageMetadata(image_format=CardImageFormat.PNG, **metadata_values)

    @pytest.mark.parametrize(
        ("image_state", "thumbnail_url", "image_metadata", "thumbnail_metadata"),
        [
            (
                CardImageState.PENDING,
                "/uploads/cards/thumb.webp",
                CardImageMetadata(CardImageFormat.PNG, 1_000, 600, 840),
                CardThumbnailMetadata(CardImageFormat.WEBP, 500, 200, 280),
            ),
            (
                CardImageState.READY,
                None,
                CardImageMetadata(CardImageFormat.PNG, 1_000, 600, 840),
                CardThumbnailMetadata(CardImageFormat.WEBP, 500, 200, 280),
            ),
            (
                CardImageState.READY,
                "/uploads/cards/thumb.webp",
                None,
                CardThumbnailMetadata(CardImageFormat.WEBP, 500, 200, 280),
            ),
            (
                CardImageState.READY,
                "/uploads/cards/thumb.webp",
                CardImageMetadata(CardImageFormat.PNG, 1_000, 600, 840),
                None,
            ),
        ],
    )
    def test_card_is_unavailable_when_any_ready_condition_is_missing(
        self,
        image_state: CardImageState,
        thumbnail_url: str | None,
        image_metadata: CardImageMetadata | None,
        thumbnail_metadata: CardThumbnailMetadata | None,
    ) -> None:
        card = self.create_card(
            image_state=image_state,
            thumbnail_url=thumbnail_url,
            image_metadata=image_metadata,
            thumbnail_metadata=thumbnail_metadata,
        )
        assert card.available_to_players is False


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
