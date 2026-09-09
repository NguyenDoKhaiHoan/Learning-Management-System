"""Export/verify reviewed API schemas without connecting to MySQL or loading secrets."""

import argparse
import json
from pathlib import Path

from src.config.config import Settings
from src.core.contracts import CurrentUser, ErrorResponse, SuccessResponse
from src.main import create_app

root = Path(__file__).resolve().parents[2] / "shared/contracts"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="schema-export-placeholder-" * 3,
        database_url="mysql+aiomysql://unused:unused@localhost/unused",
    )
    schemas = {
        "error.schema.json": ErrorResponse.model_json_schema(),
        "auth-me.schema.json": SuccessResponse[CurrentUser].model_json_schema(),
        "openapi.json": create_app(settings).openapi(),
    }
    root.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas.items():
        encoded = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path = root / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != encoded:
                raise SystemExit(f"Contract drift: regenerate {name}")
        else:
            path.write_text(encoded, encoding="utf-8")
    print("Shared contracts verified" if args.check else "Shared contracts exported")


if __name__ == "__main__":
    main()
