"""정보통신산업진흥원(NIPA): 보도자료 게시판.

목록 /home/4-4-1?curPage=N  → 표(table.tb01) 행: 번호, 제목(/home/4-4-1/{글번호}), 작성자, 첨부, 조회수, 작성일
상세 /home/4-4-1/{글번호}   → 표(table.tb05): 제목, 작성자·작성일, '내용', '첨부파일'(/comm/getFile?...)
보도자료마다 pdf와 "보도자료(HWPX)및사진.zip"이 함께 올라온다. pdf가 있으면 zip은 pick_attachments가 뺀다.
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, pick_attachments

BASE = "https://www.nipa.kr"
BOARDS = [("press", "/home/4-4-1")]
MAX_PAGES = 5
DATE = re.compile(r"20\d\d-\d\d-\d\d")


def parse_list(html: str, path: str) -> list[tuple[str, str, str]]:
    """(글번호, 제목, 작성일) 목록."""
    s = BeautifulSoup(html, "html.parser")
    out = []
    for tr in s.select("table.tb01 tbody tr"):
        a = tr.find("a", href=re.compile(re.escape(path) + r"/\d+$"))
        date = DATE.search(tr.get_text(" "))
        if a and date:
            out.append((a["href"].rsplit("/", 1)[1], " ".join(a.get_text(" ", strip=True).split()), date.group()))
    return out


def parse_detail(html: str, url: str) -> tuple[str, list[Attachment]]:
    """(본문, 첨부)."""
    s = BeautifulSoup(html, "html.parser")
    body = ""
    for td in s.select("table.tb05 td"):
        if td.get_text(strip=True) == "내용" and td.find_next_sibling("td"):
            body = " ".join(td.find_next_sibling("td").get_text(" ", strip=True).split())
            break
    atts = []
    for a in s.find_all("a", href=re.compile(r"/comm/getFile")):
        name = re.sub(r"\s*\(파일크기:[^)]*\)\s*$", "", " ".join(a.get_text(" ", strip=True).split()))
        atts.append(Attachment(name, urljoin(url, a["href"])))
    return body, atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, path in BOARDS:
        for page in range(1, MAX_PAGES + 1):
            res = http.get(f"{BASE}{path}", params={"curPage": page})
            res.raise_for_status()
            rows = parse_list(res.text, path)
            for no, title, date in rows:
                if date < since.isoformat():
                    continue
                url = f"{BASE}{path}/{no}"
                d = http.get(url)
                d.raise_for_status()
                body, atts = parse_detail(d.text, url)
                out.append(Post("NIPA", kind, no, title, date, url, body=body, attachments=pick_attachments(atts)))
            if not rows or min(r[2] for r in rows) < since.isoformat():
                break
    return out
