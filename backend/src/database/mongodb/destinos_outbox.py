"""Destinos MongoDB que el consumidor Outbox admite en aislamiento."""

PREFIJOS_MONGO_1F = ("pokearena_gridfs_test_", "pokearena_outbox_")
MONGO_F5_SERVIDOR = ("127.0.0.1", 27029)
MONGO_F5_SERVIDORES = {("127.0.0.1", 27029), ("127.0.0.1", 27017), ("localhost", 27017)}
MONGO_F5_BASE = "pokearena_catalog_frontend_dev"
