"""수집기 공통: 게시글·첨부 자료형, HTTP 세션."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

UA = "policy-harvest/0.1 (+https://github.com/opethianist-stack/policy-harvest)"
DELAY = 1.0  # 같은 기관에 보내는 요청 사이 간격(초)
PREFERRED_EXT = ("pdf", "hwpx", "hwp", "odt")  # 앞 3개는 Policy Fit 색인 형식, odt는 저장할 때 PDF로 변환한다


@dataclass
class Attachment:
    name: str
    url: str

    @property
    def ext(self) -> str:
        stem, dot, ext = self.name.rpartition(".")
        return ext.lower() if dot else ""


@dataclass
class Post:
    agency: str       # sources.yaml 의 id
    kind: str         # press / policy / notice / disclosure
    post_id: str
    title: str
    posted_at: str    # YYYY-MM-DD
    url: str
    dept: str = ""
    body: str = ""
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.agency}:{self.kind}:{self.post_id}"


def pick_attachments(atts: list[Attachment]) -> list[Attachment]:
    """같은 문서가 여러 형식으로 올라온 경우(예: 보도자료.hwpx + 보도자료.odt) 하나만 남긴다.
    색인되는 형식(pdf > hwpx > hwp)을 우선하고, 색인 형식이 없는 문서는 그대로 둔다."""
    groups: dict[str, list[Attachment]] = {}
    for a in atts:
        stem = a.name.rsplit(".", 1)[0].strip().lower()
        groups.setdefault(stem, []).append(a)
    out = []
    for group in groups.values():
        rank = lambda a: PREFERRED_EXT.index(a.ext) if a.ext in PREFERRED_EXT else len(PREFERRED_EXT)
        out.append(min(group, key=rank))
    return out


class Http:
    """User-Agent를 밝히고 요청 사이 간격을 두는 세션."""

    def __init__(self, delay: float = DELAY):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
        self.delay = delay
        self._last = 0.0

    def get(self, url: str, **kw) -> requests.Response:
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return self.s.get(url, timeout=kw.pop("timeout", 30), **kw)
        finally:
            self._last = time.monotonic()
