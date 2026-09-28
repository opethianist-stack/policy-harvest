"""수집기 공통: 게시글·첨부 자료형, HTTP 세션."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field

import requests
import urllib3

UA = "policy-harvest/0.1 (+https://github.com/opethianist-stack/policy-harvest)"
DELAY = 1.0  # 같은 기관에 보내는 요청 사이 간격(초)
RETRY_WAITS = (10, 30)  # 연결 실패·타임아웃 때 다시 시도하기 전 대기(초). 공공데이터포털이 가끔 연결을 받지 않는다
PREFERRED_EXT = ("pdf", "hwpx", "hwp", "odt")  # 앞 3개는 Policy Fit 색인 형식, odt는 저장할 때 PDF로 변환한다
REDUNDANT_ZIP = re.compile(r"사진|photo|hwpx?|한글", re.I)
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp"}  # 글자가 없어 색인되지 않으므로 받지 않는다


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
    색인되는 형식(pdf > hwpx > hwp)을 우선하고, 색인 형식이 없는 문서는 그대로 둔다. 이미지는 뺀다."""
    groups: dict[str, list[Attachment]] = {}
    for a in atts:
        if a.ext in IMAGE_EXT:
            continue
        stem = a.name.rsplit(".", 1)[0].strip().lower()
        groups.setdefault(stem, []).append(a)
    out = []
    for group in groups.values():
        rank = lambda a: PREFERRED_EXT.index(a.ext) if a.ext in PREFERRED_EXT else len(PREFERRED_EXT)
        out.append(min(group, key=rank))
    # "보도자료(HWPX)및사진.zip"처럼 같은 문서의 다른 형식·사진을 묶은 압축은 색인 형식 파일이 있으면 뺀다
    if any(a.ext in PREFERRED_EXT[:3] for a in out):
        out = [a for a in out if not (a.ext == "zip" and REDUNDANT_ZIP.search(a.name))]
    return out


class Http:
    """User-Agent를 밝히고 요청 사이 간격을 두는 세션."""

    def __init__(self, delay: float = DELAY):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
        self.delay = delay
        self._last = 0.0

    def get(self, url: str, **kw) -> requests.Response:
        timeout = kw.pop("timeout", 30)
        for retry_wait in (*RETRY_WAITS, None):
            wait = self._last + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                try:
                    return self.s.get(url, timeout=timeout, **kw)
                except requests.exceptions.SSLError:
                    # 중간 인증서를 빠뜨린 공공기관 사이트가 있다(울산교육청). 공개 페이지를 읽기만 하므로 검증 없이 다시 받는다
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    return self.s.get(url, timeout=timeout, verify=False, **kw)
            except (requests.ConnectionError, requests.Timeout):
                if retry_wait is None:
                    raise
                time.sleep(retry_wait)
            finally:
                self._last = time.monotonic()


def collect_board(http: Http, agency: str, kind: str, list_url: str, page_params, parse_list, detail_url,
                  parse_detail, since, max_pages: int = 20) -> list[Post]:
    """목록 → 상세를 따라가는 게시판 공통 흐름.

    parse_list(html) -> [(글번호, 제목, 'YYYY-MM-DD')], parse_detail(html, url) -> (본문, [Attachment]).
    공지로 고정된 옛 글이 목록 위에 붙는 게시판이 있어, 페이지의 마지막 행 날짜가 기간 밖이면 멈춘다.
    max_pages는 안전 상한이다. 상한에 닿고도 기간 끝에 못 미치면 알린다(90일 백필에서 교육부가 5페이지로 모자랐다).
    """
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        res = http.get(list_url, params=page_params(page))
        res.raise_for_status()
        rows = [r for r in parse_list(res.text) if r[0] not in seen]
        for no, title, date in rows:
            seen.add(no)
            if date < since.isoformat():
                continue
            url = detail_url(no)
            d = http.get(url)
            d.raise_for_status()
            body, atts = parse_detail(d.text, url)
            out.append(Post(agency, kind, no, title, date, url, body=body, attachments=pick_attachments(atts)))
        if not rows or rows[-1][2] < since.isoformat():
            break
    else:
        print(f"[{agency}] {kind}: {max_pages}페이지 상한에 닿음, {since} 이전까지 내려가지 못했을 수 있음", file=sys.stderr)
    return out


def dotted_date(text: str) -> str | None:
    """'2026.09.18' → '2026-09-18'."""
    m = re.search(r"(20\d\d)\.(\d\d)\.(\d\d)", text)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None
