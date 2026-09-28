"""한국지능정보사회진흥원(NIA): 보도자료·공지사항.

목록 /site/nia_kor/ex/bbs/List.do?cbIdx={게시판}&pageIndex=N
  li 안의 a onclick="doBbsFView('{cbIdx}','{bcIdx}',…)" 와 게시일 YYYY.MM.DD. 공지사항은 옛 고정 글(li.nia_noti)이 위에 붙는다
상세 /site/nia_kor/ex/bbs/View.do?cbIdx=&bcIdx=&parentSeq= (함수가 폼을 제출하지만 GET으로도 열린다)
  본문 .con_area, 첨부 .fileNew_area a[href*=Download.do] (같은 파일 링크가 두 번 나온다)
공지사항에는 업무계획이 올라온다. 모집·채용 공지도 섞여 있어 분류에서 거른다.
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, collect_board, dotted_date

BASE = "https://www.nia.or.kr"
BOARDS = [("press", "90549"), ("notice", "99835")]


def parse_list(html: str, cb: str) -> list[tuple[str, str, str]]:
    s = BeautifulSoup(html, "html.parser")
    out = []
    for a in s.find_all("a", onclick=re.compile(rf"doBbsFView\('{cb}','\d+'")):
        no = re.search(rf"doBbsFView\('{cb}','(\d+)'", a["onclick"]).group(1)
        box = a.find_parent("li") or a.parent
        date = dotted_date(box.get_text(" "))
        # 링크 글자에는 "첨부파일 있음"·날짜가 섞여 있어 title 속성("제목-첨부파일 있음")을 쓴다
        title = re.sub(r"-(첨부파일 (있음|없음)|새 ?글)$", "", a.get("title") or "").strip() or \
            " ".join(a.get_text(" ", strip=True).split())
        if date:
            out.append((no, title, date))
    return out


def parse_detail(html: str, url: str) -> tuple[str, list[Attachment]]:
    s = BeautifulSoup(html, "html.parser")
    con = s.select_one(".con_area")
    body = " ".join(con.get_text(" ", strip=True).split()) if con else ""
    atts, seen = [], set()
    for a in s.select(".fileNew_area a[href*='Download.do']"):
        href = urljoin(url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        name = re.sub(r"-다운로드$", "", " ".join(a.get_text(" ", strip=True).split()))
        atts.append(Attachment(name, href))
    return body, atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, cb in BOARDS:
        out += collect_board(
            http, "NIA", kind, f"{BASE}/site/nia_kor/ex/bbs/List.do",
            lambda page, cb=cb: {"cbIdx": cb, "pageIndex": page},
            lambda html, cb=cb: parse_list(html, cb),
            lambda no, cb=cb: f"{BASE}/site/nia_kor/ex/bbs/View.do?cbIdx={cb}&bcIdx={no}&parentSeq={no}",
            parse_detail, since)
    return out
