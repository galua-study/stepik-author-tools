"""Read-only Stepik API transport. Never falls back to student-visible answer data."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward author tokens to another endpoint.


class StepikClient:
    def __init__(self, token: str | None = None, timeout: float = 30):
        self.token = token if token is not None else os.environ.get("STEPIK_TOKEN")
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def get(self, resource: str, object_id: int | None = None, **params) -> list[dict]:
        if resource not in {"courses", "sections", "units", "lessons", "steps", "step-sources"}:
            raise ValueError("Unsupported API resource")
        if object_id is not None and (not isinstance(object_id, int) or object_id <= 0):
            raise ValueError("API IDs must be positive integers")
        path = resource + (f"/{object_id}" if object_id is not None else "")
        result, page = [], 1
        while True:
            url = "https://stepik.org/api/" + path + "?" + urlencode(dict(params, page=page), doseq=True)
            headers = {"Accept": "application/json", "User-Agent": "stepik-author-tools/0.1"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            try:
                with self.opener.open(Request(url, headers=headers), timeout=self.timeout) as response:
                    data = json.load(response)
            except HTTPError as error:
                raise ValueError(f"Stepik GET {path}: HTTP {error.code}; author source access may require STEPIK_TOKEN") from None
            except (URLError, TimeoutError, OSError, ValueError):
                raise ValueError(f"Stepik GET {path}: network failure or invalid JSON") from None
            if not isinstance(data, dict) or not isinstance(data.get(resource), list):
                raise ValueError(f"Invalid Stepik {resource} response")
            result.extend(data[resource])
            if not data.get("meta", {}).get("has_next", False):
                return result
            page += 1
            if page > 10000:
                raise ValueError("Stepik pagination did not terminate")

    def snapshot(self, course, scope: str | None = None) -> dict:
        rows = []
        for topic in course.topics(scope):
            lesson_id = topic.get("lesson_id")
            if not lesson_id:
                raise ValueError("Live comparison requires lesson_id in every selected topic")
            lessons = self.get("lessons", lesson_id)
            if len(lessons) != 1:
                raise ValueError("Lesson unavailable")
            for step_id in lessons[0]["steps"]:
                sources = self.get("step-sources", step_id)
                if len(sources) != 1:
                    raise ValueError("Author step source unavailable; refusing an incomplete snapshot")
                rows.extend(sources)
        return normalize_snapshot({"step-sources": rows})


def normalize_snapshot(data: dict) -> dict:
    if "step-sources" in data:
        return {"version": 1, "steps": [dict(stepik_id=int(s["id"]), lesson=s["lesson"], position=s["position"], block=s["block"]) for s in data["step-sources"]]}
    if data.get("version") != 1 or not isinstance(data.get("steps"), list):
        raise ValueError("Expected version 1 snapshot or Stepik step-sources response")
    return data


def read_snapshot(path: str | Path) -> dict:
    return normalize_snapshot(json.loads(Path(path).read_text(encoding="utf-8-sig")))
