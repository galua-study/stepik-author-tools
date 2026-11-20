"""Test isolation: no unit or integration test may access the live Stepik network."""

from urllib.request import Request

import pytest

from stepik_author_tools.api.client import UrllibTransport


def _reject_network(self: UrllibTransport, request: Request, timeout: float) -> bytes:
    raise AssertionError("Tests must inject a fake HTTP transport")


@pytest.fixture(autouse=True)
def prevent_live_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(UrllibTransport, "get", _reject_network)
