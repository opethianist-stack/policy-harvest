"""고용노동부(MOEL): 정책자료실.

보도자료는 받지 않는다(소속기관 행사 소식이 대부분이라 2026-09-28 담당자 결정으로 뺌). 게시판 구조는 다시 넣을 때를 위해 남겨 둔다

보도자료 목록 /news/enews/report/enewsList.do?pageIndex=N → 표(table.tstyle_list), a href="enewsView.do?news_seq=N", 등록일 YYYY.MM.DD
정책자료실 목록 /policy/policydata/list.do?pageIndex=N → a href="view.do?bbs_seq=N"
상세 본문 .b_content, 첨부 div.file a[href*=downloadFile.do] (파일명 링크와 "다운로드" 링크가 같은 주소)
업무보고(/policy/busireport/main.do)는 스크립트로 그리는 페이지라 받지 않는다. 주요업무 추진계획은 정책자료실에 올라온다
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, collect_board, dotted_date

BASE = "https://www.moel.go.kr"
BOARDS = [
    # (kind, 목록, 상세 주소 정규식, 상세 주소 틀)
    # ("press", "/news/enews/report/enewsList.do", r"enewsView\.do\?news_seq=(\d+)", "/news/enews/report/enewsView.do?news_seq={}"),
    ("policy", "/policy/policydata/list.do", r"view\.do\?bbs_seq=(\d+)", "/policy/policydata/view.do?bbs_seq={}"),
]


def parse_list(html: str, pattern: str) -> list[tuple[str, str, str]]:
    s = BeautifulSoup(html, "html.parser")
    out = []
    for a in s.find_all("a", href=re.compile(pattern)):
        row = a.find_parent("tr")
        date = dotted_date(row.get_text(" ") if row else "")
        if date:
            out.append((re.search(pattern, a["href"]).group(1), " ".join(a.get_text(" ", strip=True).split()), date))
    return out


def parse_detail(html: str, url: str) -> tuple[str, list[Attachment]]:
    s = BeautifulSoup(html, "html.parser")
    con = s.select_one(".b_content")
    body = " ".join(con.get_text(" ", strip=True).split()) if con else ""
    atts, seen = [], set()
    for a in s.find_all("a", href=re.compile(r"downloadFile\.do")):
        name = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(url, a["href"])
        if name == "다운로드" or href in seen:
            continue
        seen.add(href)
        atts.append(Attachment(name, href))
    return body, atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, path, pattern, detail in BOARDS:
        out += collect_board(
            http, "MOEL", kind, BASE + path, lambda page: {"pageIndex": page},
            lambda html, pattern=pattern: parse_list(html, pattern),
            lambda no, detail=detail: BASE + detail.format(no), parse_detail, since)
    return out
