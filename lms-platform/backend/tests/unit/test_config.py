import pytest
from pydantic import ValidationError

from src.config.config import Settings


def settings(**overrides: object) -> Settings:
    values = {
        "database_url": "mysql+aiomysql://user:pass@localhost/lms",
        "jwt_secret": "a" * 48,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_connection_charset_and_secret_redaction() -> None:
    config = settings()
    assert config.sqlalchemy_url.query["charset"] == "utf8mb4"
    assert "a" * 48 not in repr(config)
    assert "user:pass" not in repr(config)


@pytest.mark.parametrize(
    "url", ["sqlite:///x", "mysql://u:p@host/db", "mysql+aiomysql://u:p@host/db?charset=latin1"]
)
def test_reject_wrong_database(url: str) -> None:
    with pytest.raises(ValidationError):
        settings(database_url=url)


def test_reject_placeholder_and_short_secret() -> None:
    for secret in ("short", "replace-with-a-random-secret-at-least-32-characters"):
        with pytest.raises(ValidationError):
            settings(jwt_secret=secret)


def test_password_with_percent_escape() -> None:
    config = settings(database_url="mysql+aiomysql://u:p%40ss%25word@localhost/db")
    assert config.sqlalchemy_url.password == "p@ss%word"


def test_docker_host_override_preserves_credentials() -> None:
    config = settings(
        database_url="mysql+aiomysql://u:p%40ss%25word@127.0.0.1:3306/lms",
        db_host_override="host.docker.internal",
    )
    assert config.sqlalchemy_url.host == "host.docker.internal"
    assert config.sqlalchemy_url.database == "lms"
    assert config.sqlalchemy_url.password == "p@ss%word"
