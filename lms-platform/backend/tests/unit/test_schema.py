from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from src.core.database.models.registry import Base

BACKEND = Path(__file__).resolve().parents[2]


def test_mysql_ddl_and_foreign_key_indexes() -> None:
    assert len(Base.metadata.tables) == 14
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert "ENGINE=InnoDB" in ddl
        assert "CHARSET=utf8mb4" in ddl
        assert "COLLATE utf8mb4_unicode_ci" in ddl
        assert {"id", "created_at", "updated_at"} <= set(table.c.keys())
        assert "ON UPDATE CURRENT_TIMESTAMP(6)" in ddl
        indexes = [list(index.columns.keys()) for index in table.indexes]
        indexes += [
            list(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)
        ]
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete == "RESTRICT"
            assert any(columns[0] == foreign_key.parent.name for columns in indexes)


def test_offline_upgrade_and_downgrade() -> None:
    output = StringIO()
    config = Config(str(BACKEND / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for name in Base.metadata.tables:
        assert f"CREATE TABLE {name} (" in sql
    output.truncate(0)
    output.seek(0)
    command.downgrade(config, "0001_p0:base", sql=True)
    assert output.getvalue().count("DROP TABLE") == 14  # Alembic retains its empty version table
