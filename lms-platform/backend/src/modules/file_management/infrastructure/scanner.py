"""Fail-closed ClamAV INSTREAM adapter with a local-only EICAR test guard."""

import asyncio
import hashlib
import logging
import struct
from contextlib import suppress

from fastapi import HTTPException

logger = logging.getLogger("lms")
EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"


def development_scan(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(65536):
            digest.update(chunk)
    return digest.hexdigest() != EICAR_SHA256


async def scan_file(path, settings):
    writer = None
    try:
        async with asyncio.timeout(settings.file_scan_timeout_seconds):
            if settings.file_scan_backend == "development":
                clean = await asyncio.to_thread(development_scan, path)
                engine = "development-eicar"
            else:
                reader, writer = await asyncio.open_connection(
                    settings.file_scan_host,
                    settings.file_scan_port,
                    limit=4096,
                )
                writer.write(b"zINSTREAM\x00")
                with path.open("rb") as source:
                    while chunk := await asyncio.to_thread(source.read, 65536):
                        writer.write(struct.pack("!I", len(chunk)) + chunk)
                        await writer.drain()
                writer.write(b"\x00\x00\x00\x00")
                await writer.drain()
                response = (await reader.readuntil(b"\x00"))[:-1]
                if response == b"stream: OK":
                    clean = True
                elif response.startswith(b"stream: ") and response.endswith(b" FOUND"):
                    clean = False
                else:
                    raise ValueError("Unexpected scanner response")
                engine = "clamd"
            if not clean:
                logger.warning("file_scan_rejected")
                raise HTTPException(422, "File was rejected by the security scanner")
            return engine
    except HTTPException:
        raise
    except (
        OSError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
        ValueError,
    ):
        logger.warning("file_scan_unavailable")
        raise HTTPException(503, "File scanner unavailable; retry later") from None
    finally:
        if writer is not None:
            writer.close()
            with suppress(OSError):
                await writer.wait_closed()
