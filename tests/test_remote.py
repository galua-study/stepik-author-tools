from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from stepik_author_tools import StepikClient


class FakeOpener:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return BytesIO(json.dumps(page).encode())


def test_pagination_and_get_only():
    client = StepikClient(token="synthetic-test-token")
    client.opener = FakeOpener([
        {"lessons": [{"id": 1}], "meta": {"has_next": True}},
        {"lessons": [{"id": 2}], "meta": {"has_next": False}},
    ])
    assert len(client.get("lessons")) == 2
    assert "page=2" in client.opener.requests[1].full_url
    assert all(r.get_method() == "GET" for r in client.opener.requests)


def test_access_error_never_echoes_response_or_token():
    client = StepikClient(token="private-test-value")
    client.opener = FakeOpener([HTTPError("https://stepik.org", 403, "private-test-value", {}, None)])
    with pytest.raises(ValueError, match="HTTP 403") as error:
        client.get("step-sources", 1)
    assert "private-test-value" not in str(error.value)


def test_snapshot_fetches_every_source_and_refuses_missing(project=None):
    from types import SimpleNamespace
    client = StepikClient()
    client.opener = FakeOpener([
        {"lessons": [{"id": 1, "steps": [2, 3]}]},
        {"step-sources": [{"id": 2, "lesson": 1, "position": 1, "block": {"name": "text", "text": "Hi"}}]},
        {"step-sources": []},
    ])
    course = SimpleNamespace(topics=lambda scope: [{"lesson_id": 1}])
    with pytest.raises(ValueError, match="incomplete"):
        client.snapshot(course)
