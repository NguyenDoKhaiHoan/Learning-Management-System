from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.config.config import Settings
from src.main import create_app


@pytest.mark.parametrize("available", [True, False])
def test_readiness_and_liveness(available: bool) -> None:
    settings = Settings(
        _env_file=None, database_url="mysql+aiomysql://u:p@localhost/lms", jwt_secret="x" * 48
    )
    with TestClient(create_app(settings)) as client:
        session = AsyncMock()
        if not available:
            session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private"))
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=session)
        context.__aexit__ = AsyncMock(return_value=False)
        client.app.state.session_factory = MagicMock(return_value=context)
        assert client.get("/livez").status_code == 200
        response = client.get("/healthz")
        assert response.status_code == (200 if available else 503)
        assert "private" not in response.text
