"""Transport contract tests: pagination, author access, errors and response validation."""

import json
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from stepik_author_tools import StepikClient, load_settings
from stepik_author_tools.course.project import Course
from stepik_author_tools.domain.models import JsonObject

_RECAP_SOURCE: JsonObject = {
    "step-sources": [
        {"id": 910007, "lesson": 900002, "position": 1, "block": {"name": "text", "text": "Hi"}}
    ]
}


class FakeTransport:
    def __init__(self, pages: list[JsonObject | Exception]) -> None:
        self.pages = iter(pages)
        self.calls: list[tuple[Request, float]] = []

    def get(self, request: Request, timeout: float) -> bytes:
        self.calls.append((request, timeout))
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return json.dumps(page).encode()


def test_pagination_and_get_only() -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 1}], "meta": {"has_next": True}},
            {"lessons": [{"id": 2}], "meta": {"has_next": False}},
        ]
    )
    client = StepikClient(token="synthetic-test-token", timeout=2.5, transport=transport)
    assert len(client.get("lessons")) == 2
    assert "page=2" in transport.calls[1][0].full_url
    assert [(request.get_method(), timeout) for request, timeout in transport.calls] == [
        ("GET", 2.5),
        ("GET", 2.5),
    ]


def test_access_error_never_echoes_response_or_token() -> None:
    error = HTTPError("https://stepik.org", 403, "private-test-value", Message(), None)
    client = StepikClient(token="private-test-value", transport=FakeTransport([error]))
    with pytest.raises(ValueError, match="HTTP 403") as caught:
        client.get("step-sources", 1)
    assert "private-test-value" not in str(caught.value)


def test_snapshot_fetches_every_source_and_refuses_missing(project: Course) -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 900002, "steps": [910007, 910008]}]},
            _RECAP_SOURCE,
            {"step-sources": []},
        ]
    )
    client = StepikClient(transport=transport)
    with pytest.raises(ValueError, match="incomplete"):
        client.snapshot(project, scope="recap")


def test_successful_author_snapshot_uses_injected_transport(project: Course) -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 900002, "steps": [910007]}]},
            _RECAP_SOURCE,
        ]
    )
    snapshot = StepikClient(transport=transport).snapshot(project, scope="recap")
    assert snapshot.steps[0].stepik_id == 910007
    assert [request.full_url for request, _ in transport.calls] == [
        "https://stepik.org/api/lessons/900002?page=1",
        "https://stepik.org/api/step-sources/910007?page=1",
    ]


def test_malformed_pagination_flag_is_not_treated_as_truthy() -> None:
    client = StepikClient(
        transport=FakeTransport(
            [
                {"lessons": [], "meta": {"has_next": "false"}},
            ]
        )
    )
    with pytest.raises(ValueError, match="has_next"):
        client.get("lessons")


def test_profile_controls_endpoint_resources_limit_and_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "mirror.toml"
    config.write_text(
        '[api]\nbase_url = "https://mirror.example/api/v2"\nresources = ["catalog"]\n'
        "max_pages = 1\ntimeout = 2.5",
        encoding="utf-8",
    )
    monkeypatch.setenv("STEPIK_TOKEN", "synthetic")
    transport = FakeTransport([{"catalog": [], "meta": {"has_next": True}}])
    client = StepikClient(settings=load_settings(config).api, transport=transport)
    with pytest.raises(ValueError, match="Unsupported"):
        client.get("lessons")
    with pytest.raises(ValueError, match="pagination"):
        client.get("catalog")
    ((request, timeout),) = transport.calls
    assert request.full_url == "https://mirror.example/api/v2/catalog?page=1"
    assert timeout == 2.5
    assert not request.has_header("Authorization")
