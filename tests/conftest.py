"""Test isolation: no unit or integration test may access the live Stepik network."""

import shutil
from pathlib import Path
from urllib.request import Request

import pytest

from stepik_author_tools import load_course
from stepik_author_tools.api.client import UrllibTransport
from stepik_author_tools.course.project import Course
from tests.helpers import DEMO


def _reject_network(self: UrllibTransport, request: Request, timeout: float) -> bytes:
    raise AssertionError("Tests must inject a fake HTTP transport")


@pytest.fixture(autouse=True)
def prevent_live_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(UrllibTransport, "get", _reject_network)


@pytest.fixture
def project(tmp_path: Path) -> Course:
    target = tmp_path / "demo"
    shutil.copytree(DEMO, target)
    return load_course(target)
