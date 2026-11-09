"""Revisiones compatibles con el backend de Crear Carta y el login local."""

REVISION_IDENTIDAD_LOCAL = "1g_local_master_admin"
REVISIONES_IDENTIDAD_LOCAL = frozenset({
    REVISION_IDENTIDAD_LOCAL,
    "011_locations_full",
    "012_player_profiles_inventory",
})
REVISIONES_CARTAS = frozenset({
    "1b2b_card_image_integrity",
    REVISION_IDENTIDAD_LOCAL,
    "011_locations_full",
    "012_player_profiles_inventory",
})
