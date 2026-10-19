"""ClamAV INSTREAM framing, clean/infected responses and fail-closed errors."""

import asyncio
import struct

import pytest
from fastapi import HTTPException

from src.config.config import Settings
from src.modules.file_management.infrastructure.scanner import scan_file


def settings(port, backend="clamd"):
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="mysql+aiomysql://user:pass@localhost/lms",
        jwt_secret="scanner-test-secret-" * 3,
        file_scan_backend=backend,
        file_scan_port=port,
        file_scan_timeout_seconds=2,
    )


async def scanner_server(response, received):
    async def handle(reader, writer):
        assert await reader.readuntil(b"\x00") == b"zINSTREAM\x00"
        while True:
            size = struct.unpack("!I", await reader.readexactly(4))[0]
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(response + b"\x00")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    return await asyncio.start_server(handle, "127.0.0.1", 0)


@pytest.mark.parametrize(
    ("response", "status"),
    [(b"stream: OK", None), (b"stream: Test-Signature FOUND", 422), (b"broken", 503)],
)
async def test_clamd_stream_protocol(tmp_path, response, status):
    payload = b"%PDF-1.7\nscan this private content"
    path = tmp_path / "upload"
    path.write_bytes(payload)
    received = bytearray()
    server = await scanner_server(response, received)
    port = server.sockets[0].getsockname()[1]
    async with server:
        if status is None:
            assert await scan_file(path, settings(port)) == "clamd"
        else:
            with pytest.raises(HTTPException) as error:
                await scan_file(path, settings(port))
            assert error.value.status_code == status
    assert received == payload


async def test_development_clean_and_connection_failure_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "clean.pdf"
    path.write_bytes(b"%PDF-1.7\nclean")
    assert await scan_file(path, settings(1, "development")) == "development-eicar"

    async def unavailable(*_args, **_kwargs):
        raise OSError("scanner offline")

    monkeypatch.setattr(asyncio, "open_connection", unavailable)
    with pytest.raises(HTTPException) as error:
        await scan_file(path, settings(3310))
    assert error.value.status_code == 503
