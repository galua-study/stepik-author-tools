"""Read-only Stepik HTTP client with injectable transport and bounded pagination."""

import json
import os
from typing import Protocol, TypeAlias
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import TypeAdapter

from ..domain.models import JsonObject, PositiveId, Snapshot, TopicSpec
from ..domain.stepik import LessonSteps, PageMetadata
from ..serialization.jsonio import array_value, object_value
from ..serialization.snapshots import normalize_snapshot

QueryValue: TypeAlias = str | int | bool | list[str | int]
_RESOURCES = {"courses", "sections", "units", "lessons", "steps", "step-sources"}
_API_ROOT = "https://stepik.org/api/"
_MAX_PAGES = 10_000
_API_ID = TypeAdapter(PositiveId)


class Transport(Protocol):
    """Minimal HTTP boundary; test doubles do not need urllib implementation details."""

    def get(self, request: Request, timeout: float) -> bytes:
        """Perform one GET and return its complete response body."""
        ...


class TopicProvider(Protocol):
    """Only the manifest selection operation needed to fetch a snapshot."""

    def topics(self, scope: str | None = None) -> list[TopicSpec]:
        """Return selected topics with lesson IDs."""
        ...


class NoRedirect(HTTPRedirectHandler):
    """Refuse redirects so author credentials cannot be forwarded to another host."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        """Decline every redirect, regardless of its status or destination."""
        return None


class UrllibTransport:
    """Default transport with TLS verification and redirect rejection."""

    def __init__(self) -> None:
        self._opener = build_opener(NoRedirect())

    def get(self, request: Request, timeout: float) -> bytes:
        """Read one response while guaranteeing that its stream is closed."""
        with self._opener.open(request, timeout=timeout) as response:
            content = response.read()
        if not isinstance(content, bytes):
            raise ValueError("HTTP transport returned a non-binary body")
        return content


class StepikClient:
    """Fetch public/author resources without any POST, PUT or DELETE capability."""

    def __init__(
        self, token: str | None = None, timeout: float = 30, *, transport: Transport | None = None
    ) -> None:
        self.token = token if token is not None else os.environ.get("STEPIK_TOKEN")
        self.timeout = timeout
        self.transport = transport if transport is not None else UrllibTransport()

    def _page(self, path: str, query: dict[str, QueryValue]) -> JsonObject:
        headers = {"Accept": "application/json", "User-Agent": "stepik-author-tools/0.1"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(_API_ROOT + path + "?" + urlencode(query, doseq=True), headers=headers)
        try:
            return object_value(
                json.loads(self.transport.get(request, self.timeout)), "API response"
            )
        except HTTPError as error:
            # Response bodies and exception strings may contain credentials/content.
            raise ValueError(
                f"Stepik GET {path}: HTTP {error.code}; "
                "author source access may require STEPIK_TOKEN"
            ) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ValueError(f"Stepik GET {path}: network failure or invalid JSON") from None

    def get(
        self, resource: str, object_id: int | None = None, **params: QueryValue
    ) -> list[JsonObject]:
        """Read a supported resource, following all pages with no fixed page-size assumption."""
        if resource not in _RESOURCES:
            raise ValueError("Unsupported API resource")
        if object_id is not None:
            _API_ID.validate_python(object_id, strict=True)
        path = resource + (f"/{object_id}" if object_id is not None else "")
        result: list[JsonObject] = []
        for page in range(1, _MAX_PAGES + 1):
            data = self._page(path, dict(params, page=page))
            result.extend(
                object_value(row, resource) for row in array_value(data.get(resource), resource)
            )
            meta = PageMetadata.model_validate(data.get("meta", {}))
            if not meta.has_next:
                return result
        raise ValueError("Stepik pagination did not terminate")

    def _lesson_sources(self, lesson_id: int) -> list[JsonObject]:
        lessons = self.get("lessons", lesson_id)
        if len(lessons) != 1:
            raise ValueError("Lesson unavailable")
        rows = []
        for step_id in LessonSteps.model_validate(lessons[0]).steps:
            sources = self.get("step-sources", step_id)
            if len(sources) != 1:
                raise ValueError("Author step source unavailable; refusing an incomplete snapshot")
            rows.extend(sources)
        return rows

    def snapshot(self, course: TopicProvider, scope: str | None = None) -> Snapshot:
        """Fetch every selected lesson's author source without falling back to student data."""
        rows: list[JsonObject] = []
        for topic in course.topics(scope):
            lesson_id = topic.lesson_id
            if not lesson_id:
                raise ValueError("Live comparison requires lesson_id in every selected topic")
            rows.extend(self._lesson_sources(lesson_id))
        return normalize_snapshot({"step-sources": rows})
