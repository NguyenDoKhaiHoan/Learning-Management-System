from types import SimpleNamespace

import pytest

from scripts.seed_week2 import seed_demo


@pytest.mark.asyncio
async def test_demo_seed_refuses_application_database_before_any_sql():
    connection = SimpleNamespace(engine=SimpleNamespace(url=SimpleNamespace(database="lms")))
    with pytest.raises(ValueError, match="lms_demo_"):
        await seed_demo(connection)
