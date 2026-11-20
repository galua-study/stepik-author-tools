"""Test isolation: no unit or integration test may access the live Stepik network."""

import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from stepik_author_tools import load_course
from stepik_author_tools.api.client import UrllibTransport
from stepik_author_tools.course.project import Course
from tests.helpers import DEMO


@pytest.fixture(autouse=True)
def prevent_live_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = Mock(side_effect=AssertionError("Tests must inject a fake HTTP transport"))
    monkeypatch.setattr(UrllibTransport, "get", blocked)


@pytest.fixture
def project(tmp_path: Path) -> Course:
    target = tmp_path / "demo"
    shutil.copytree(DEMO, target)
    return load_course(target)
