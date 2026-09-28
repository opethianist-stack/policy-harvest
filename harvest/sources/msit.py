"""과학기술정보통신부: 공공데이터포털 API(보도자료·주요정책).

응답: response = [ {header}, {body: {totalCount, items: [{item: {subject, pressDt, deptName, viewUrl, files}}]}} ]
files 가 한 건이면 배열이 아닐 수 있다. 한 페이지 최대 10건, 키워드 검색 없음.
(Policy Fit lib/msit.js 와 같은 방식)
"""

from __future__ import annotations

import datetime
import os
import re
from urllib.parse import parse_qs, unquote, urlparse

from .base import Attachment, Http, Post, pick_attachments

BASE = "https://apis.data.go.kr/1721000"
FEEDS = [
    # (kind, path, 추가 파라미터)
    ("press", "/msitpressreleaseinfo/pressReleaseList", {}),
    ("policy", "/msitmainpolicyinfo/mainPolicyList", {"policyType": "POLICY01"}),  # 연구개발정책
    ("policy", "/msitmainpolicyinfo/mainPolicyList", {"policyType": "POLICY03"}),  # 정보통신정책
    ("policy", "/msitmainpolicyinfo/mainPolicyList", {"policyType": "POLICY10"}),  # 기타
]


def service_key() -> str:
    # 인코딩 키가 들어와도 동작하도록 한 번 디코딩한다(디코딩 키는 그대로)
    return unquote(os.environ.get("DATA_GO_KR_KEY", "").strip())


def as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])


def post_id(view_url: str, subject: str) -> str:
    q = parse_qs(urlparse(view_url).query)
    for k in ("nttSeqNo", "bbsSeqNo"):
        if q.get(k):
            return q[k][0]
    return re.sub(r"\W+", "", subject)[:40]


def parse(data: dict, kind: str) -> tuple[int, list[Post]]:
    arr = as_list(data.get("response"))
    header = next((x["header"] for x in arr if isinstance(x, dict) and "header" in x), {})
    body = next((x["body"] for x in arr if isinstance(x, dict) and "body" in x), None)
    if body is None:
        raise RuntimeError(f"과기정통부 API 응답 오류: {header.get('resultMsg') or data}")
    posts = []
    for it in as_list(body.get("items")):
        it = it.get("item", it) if isinstance(it, dict) else {}
        subject = re.sub(r"\s+", " ", str(it.get("subject") or "")).strip()
        if not subject:
            continue
        files = [f.get("file", f) for f in as_list(it.get("files")) if isinstance(f, dict)]
        atts = [Attachment(f.get("fileName") or "", f["fileUrl"]) for f in files if f.get("fileUrl")]
        view = it.get("viewUrl") or ""
        posts.append(Post(
            agency="MSIT", kind=kind, post_id=post_id(view, subject), title=subject,
            posted_at=str(it.get("pressDt") or "")[:10], url=view, dept=str(it.get("deptName") or "").strip(),
            attachments=pick_attachments(atts),
        ))
    return int(body.get("totalCount") or 0), posts


MAX_PAGES = {"press": 15, "policy": 3}  # 보도자료는 하루 여러 건이라 기간을 채울 때까지 넘긴다


def keep(p: Post, since: datetime.date, year: int) -> bool:
    """보도자료는 since 이후, 주요정책은 올해 게시분만(목록이 날짜순이 아니다)."""
    if p.kind == "press":
        return p.posted_at >= since.isoformat()
    return p.posted_at[:4] == str(year)


def fetch_page(http: Http, path: str, extra: dict, page: int, kind: str) -> list[Post]:
    res = http.get(BASE + path, params={"ServiceKey": service_key(), "pageNo": page, "numOfRows": 10,
                                        "returnType": "json", **extra})
    res.raise_for_status()
    try:
        data = res.json()
    except ValueError:
        raise RuntimeError(f"과기정통부 API가 JSON이 아닌 응답: {res.text[:200]}")
    return parse(data, kind)[1]


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    if not service_key():
        raise RuntimeError("DATA_GO_KR_KEY 가 없습니다")
    seen, out = set(), []
    for kind, path, extra in FEEDS:
        for page in range(1, MAX_PAGES[kind] + 1):
            posts = fetch_page(http, path, extra, page, kind)
            for p in posts:
                if p.url in seen or not keep(p, since, today.year):
                    continue
                seen.add(p.url)
                out.append(p)
            # 보도자료는 최신순이라 기간 밖 글이 나오면 멈춘다
            if not posts or (kind == "press" and min(p.posted_at for p in posts) < since.isoformat()):
                break
    return out
