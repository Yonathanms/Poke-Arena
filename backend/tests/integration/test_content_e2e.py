"""The previous E2E suite truncated shared catalog tables and Mongo collections.

Safe replacement coverage is in ``test_content_local_e2e.py`` and uses isolated
PostgreSQL, MongoDB, and filesystem resources.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Replaced by isolated-resource coverage in test_content_local_e2e.py."
)


def test_legacy_shared_database_e2e_is_disabled() -> None:
    """Ensure the old destructive test cannot be run by pytest discovery."""
