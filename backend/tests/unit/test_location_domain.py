"""Tests unitarios para US-124: Crear Ubicación (dominio)."""

import pytest

from src.modules.content.domain.entities import Location
from src.modules.content.domain.exceptions import (
    InvalidCardLimitError,
    InvalidEnergyBonusError,
    InvalidLocationEffectParamsError,
    InvalidLocationNameError,
)
from src.modules.content.domain.value_objects import (
    EnergyBonusMode,
    EnergyBonusSpec,
    LocationEffectSpec,
    LocationEffectType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_effect(
    effect_type: LocationEffectType = LocationEffectType.BONIFICACION_PODER,
    params: dict | None = None,
) -> LocationEffectSpec:
    if params is None:
        params = {"card_type": "FUE", "amount": 2}
    return LocationEffectSpec(effect_type=effect_type, description="Efecto de prueba", params=params)


def _make_location(**kwargs) -> Location:
    defaults = dict(
        name="Monte Corona",
        image_url="https://storage/img.webp",
        effect=_base_effect(),
    )
    defaults.update(kwargs)
    return Location.create(**defaults)


# ---------------------------------------------------------------------------
# Location.create — nombre
# ---------------------------------------------------------------------------

class TestLocationName:
    def test_valid_name_is_accepted(self) -> None:
        loc = _make_location(name="Ciudad Azulona")
        assert loc.name == "Ciudad Azulona"

    def test_name_is_stripped(self) -> None:
        loc = _make_location(name="  Arrecife  ")
        assert loc.name == "Arrecife"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(InvalidLocationNameError):
            _make_location(name="")

    def test_blank_name_raises(self) -> None:
        with pytest.raises(InvalidLocationNameError):
            _make_location(name="   ")

    def test_name_over_100_chars_raises(self) -> None:
        with pytest.raises(InvalidLocationNameError):
            _make_location(name="X" * 101)

    def test_name_exactly_100_chars_is_accepted(self) -> None:
        loc = _make_location(name="A" * 100)
        assert len(loc.name) == 100


# ---------------------------------------------------------------------------
# Location.create — card_limit
# ---------------------------------------------------------------------------

class TestCardLimit:
    @pytest.mark.parametrize("limit", [0, 1, 2, 3, 4, 5])
    def test_valid_card_limit_is_accepted(self, limit: int) -> None:
        loc = _make_location(card_limit=limit)
        assert loc.card_limit == limit

    def test_card_limit_negative_raises(self) -> None:
        with pytest.raises(InvalidCardLimitError):
            _make_location(card_limit=-1)

    def test_card_limit_above_5_raises(self) -> None:
        with pytest.raises(InvalidCardLimitError):
            _make_location(card_limit=6)


# ---------------------------------------------------------------------------
# EnergyBonusSpec — validación
# ---------------------------------------------------------------------------

class TestEnergyBonusSpec:
    @pytest.mark.parametrize("amount", [0, 1, 2, 3])
    def test_fija_valid_amounts(self, amount: int) -> None:
        spec = EnergyBonusSpec(mode=EnergyBonusMode.FIJA, amount=amount)
        assert spec.amount == amount

    def test_fija_amount_4_raises(self) -> None:
        with pytest.raises(InvalidEnergyBonusError):
            EnergyBonusSpec(mode=EnergyBonusMode.FIJA, amount=4)

    def test_fija_negative_raises(self) -> None:
        with pytest.raises(InvalidEnergyBonusError):
            EnergyBonusSpec(mode=EnergyBonusMode.FIJA, amount=-1)

    @pytest.mark.parametrize("amount", [0, 1, 2])
    def test_por_cartas_valid_amounts(self, amount: int) -> None:
        spec = EnergyBonusSpec(mode=EnergyBonusMode.POR_CARTAS, amount=amount)
        assert spec.amount == amount

    def test_por_cartas_amount_3_raises(self) -> None:
        with pytest.raises(InvalidEnergyBonusError):
            EnergyBonusSpec(mode=EnergyBonusMode.POR_CARTAS, amount=3)

    def test_energy_bonus_stored_on_location(self) -> None:
        spec = EnergyBonusSpec(mode=EnergyBonusMode.FIJA, amount=2)
        loc = _make_location(energy_bonus=spec)
        assert loc.energy_bonus is spec


# ---------------------------------------------------------------------------
# LocationEffectSpec.validate_params_for_creation
# ---------------------------------------------------------------------------

class TestEffectParamValidation:
    # BONIFICACION_PODER -------------------------------------------------------
    def test_bonificacion_poder_valid(self) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.BONIFICACION_PODER,
            {"card_type": "FUE", "amount": 2},
        )

    @pytest.mark.parametrize("card_type", ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"])
    def test_bonificacion_poder_all_card_types(self, card_type: str) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.BONIFICACION_PODER,
            {"card_type": card_type, "amount": 0},
        )

    @pytest.mark.parametrize("amount", [-5, -1, 0, 1, 5])
    def test_bonificacion_poder_amount_range(self, amount: int) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.BONIFICACION_PODER,
            {"card_type": "LUC", "amount": amount},
        )

    def test_bonificacion_poder_missing_card_type_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.BONIFICACION_PODER,
                {"amount": 2},
            )

    def test_bonificacion_poder_invalid_card_type_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.BONIFICACION_PODER,
                {"card_type": "INVALID", "amount": 2},
            )

    def test_bonificacion_poder_amount_out_of_range_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.BONIFICACION_PODER,
                {"card_type": "FUE", "amount": 6},
            )

    def test_bonificacion_poder_missing_amount_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.BONIFICACION_PODER,
                {"card_type": "FUE"},
            )

    # MODIFICADOR_COSTO --------------------------------------------------------
    def test_modificador_costo_valid_without_card_type(self) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.MODIFICADOR_COSTO,
            {"amount": -1},
        )

    def test_modificador_costo_valid_with_card_type(self) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.MODIFICADOR_COSTO,
            {"amount": 2, "card_type": "PSI"},
        )

    def test_modificador_costo_missing_amount_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.MODIFICADOR_COSTO,
                {},
            )

    def test_modificador_costo_invalid_card_type_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.MODIFICADOR_COSTO,
                {"amount": 1, "card_type": "FUEGO"},
            )

    def test_modificador_costo_amount_out_of_range_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.MODIFICADOR_COSTO,
                {"amount": -6},
            )

    # RESTRICCION_TURNO --------------------------------------------------------
    def test_restriccion_turno_valid(self) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.RESTRICCION_TURNO,
            {"turns": [1, 3, 5]},
        )

    def test_restriccion_turno_single_turn(self) -> None:
        LocationEffectSpec.validate_params_for_creation(
            LocationEffectType.RESTRICCION_TURNO,
            {"turns": [2]},
        )

    def test_restriccion_turno_empty_list_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.RESTRICCION_TURNO,
                {"turns": []},
            )

    def test_restriccion_turno_missing_turns_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.RESTRICCION_TURNO,
                {},
            )

    def test_restriccion_turno_zero_turn_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.RESTRICCION_TURNO,
                {"turns": [0, 2]},
            )

    def test_restriccion_turno_negative_turn_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.RESTRICCION_TURNO,
                {"turns": [-1]},
            )

    # LIMITE_CARTAS (legacy, fuera del catálogo) --------------------------------
    def test_limite_cartas_not_in_catalog_raises(self) -> None:
        with pytest.raises(InvalidLocationEffectParamsError):
            LocationEffectSpec.validate_params_for_creation(
                LocationEffectType.LIMITE_CARTAS,
                {},
            )
