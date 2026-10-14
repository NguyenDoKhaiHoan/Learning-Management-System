"""Release verification must not silently skip the real-database checks."""

import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--require-mysql",
        action="store_true",
        help="Fail before collection when MYSQL_TEST_ADMIN_URL is not configured",
    )


def pytest_configure(config):
    if config.getoption("--require-mysql") and not os.getenv("MYSQL_TEST_ADMIN_URL"):
        raise pytest.UsageError("--require-mysql needs MYSQL_TEST_ADMIN_URL; no tests were run")
