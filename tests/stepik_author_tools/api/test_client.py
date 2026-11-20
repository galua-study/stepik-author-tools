"""Transport contract tests: pagination, author access, errors and response validation."""

import json
from email.message import Message
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from stepik_author_tools import StepikClient
from stepik_author_tools.domain.models import JsonObject, TopicSpec


class FakeTransport:
    def __init__(self, pages: list[JsonObject | Exception]) -> None:
        self.pages = iter(pages)
        self.requests: list[Request] = []

    def get(self, request: Request, timeout: float) -> bytes:
        self.requests.append(request)
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return json.dumps(page).encode()


class FakeCourse:
    def topics(self, scope: str | None = None) -> list[TopicSpec]:
        return [TopicSpec(id="example", lesson_id=1, steps=[])]


def test_pagination_and_get_only() -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 1}], "meta": {"has_next": True}},
            {"lessons": [{"id": 2}], "meta": {"has_next": False}},
        ]
    )
    client = StepikClient(token="synthetic-test-token", transport=transport)
    assert len(client.get("lessons")) == 2
    assert "page=2" in transport.requests[1].full_url
    assert all(request.get_method() == "GET" for request in transport.requests)


def test_access_error_never_echoes_response_or_token() -> None:
    error = HTTPError("https://stepik.org", 403, "private-test-value", Message(), None)
    client = StepikClient(token="private-test-value", transport=FakeTransport([error]))
    with pytest.raises(ValueError, match="HTTP 403") as caught:
        client.get("step-sources", 1)
    assert "private-test-value" not in str(caught.value)


def test_snapshot_fetches_every_source_and_refuses_missing() -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 1, "steps": [2, 3]}]},
            {
                "step-sources": [
                    {"id": 2, "lesson": 1, "position": 1, "block": {"name": "text", "text": "Hi"}}
                ]
            },
            {"step-sources": []},
        ]
    )
    client = StepikClient(transport=transport)
    with pytest.raises(ValueError, match="incomplete"):
        client.snapshot(FakeCourse())


def test_successful_author_snapshot_uses_injected_transport() -> None:
    transport = FakeTransport(
        [
            {"lessons": [{"id": 1, "steps": [2]}]},
            {
                "step-sources": [
                    {"id": 2, "lesson": 1, "position": 1, "block": {"name": "text", "text": "Hi"}}
                ]
            },
        ]
    )
    snapshot = StepikClient(transport=transport).snapshot(FakeCourse())
    assert snapshot.steps[0].stepik_id == 2
    assert len(transport.requests) == 2


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
