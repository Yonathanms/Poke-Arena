"""Revisiones compatibles con el backend de Crear Carta y el login local."""

REVISION_IDENTIDAD_LOCAL = "1g_local_master_admin"
REVISION_APERTURA_INICIAL = "013_initial_pack_opened_at"
REVISION_TIPO_CUENTA = "016_card_types_and_rarities"
REVISIONES_IDENTIDAD_LOCAL = frozenset({
    REVISION_IDENTIDAD_LOCAL,
    "011_locations_full",
    "012_player_profiles_inventory",
    REVISION_APERTURA_INICIAL,
    "014_identity_account_immutable",
    "015_player_decks",
    REVISION_TIPO_CUENTA,
})
REVISIONES_CARTAS = REVISIONES_IDENTIDAD_LOCAL | {"1b2b_card_image_integrity"}

