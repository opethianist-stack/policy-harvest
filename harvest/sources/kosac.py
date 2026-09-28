"""한국과학창의재단(KOSAC): 보도자료 게시판.

Next.js 사이트지만 목록·상세 모두 서버에서 완성된 HTML이 온다.
목록 /menus/272/boards/394/posts?page=N → table.board_list 행: 번호, 구분, 제목(/posts/{글번호}?page=N), 첨부, 등록일(td.date), 조회
상세 /menus/272/boards/394/posts/{글번호}
  - 등록일: .tbl_info 의 "등록일 YYYY-MM-DD"
  - 첨부 이름: .view_file .fileBr span (다운로드 버튼 href는 비어 있고 스크립트가 연다)
  - 첨부 주소: 페이지에 실린 데이터(self.__next_f)의 fileUrl = https://cdn.kosac.re.kr/files/cms/attach/... (이름과 같은 순서)
  - 본문: .view_con
"""

from __future__ import annotations

import datetime
import re

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, pick_attachments

BASE = "https://www.kosac.re.kr"
BOARDS = [("press", "/menus/272/boards/394/posts")]
MAX_PAGES = 3
DATE = re.compile(r"20\d\d-\d\d-\d\d")
FILE_URL = re.compile(r"https://cdn\.kosac\.re\.kr/files/[^\"'\\\s<>]+")


def parse_list(html: str, path: str) -> list[tuple[str, str, str]]:
    """(글번호, 제목, 등록일) 목록."""
    s = BeautifulSoup(html, "html.parser")
    out = []
    for tr in s.select("table.board_list tbody tr"):
        a = tr.find("a", href=re.compile(re.escape(path) + r"/\d+"))
        td = tr.select_one("td.date")
        date = DATE.search(td.get_text() if td else tr.get_text(" "))
        if a and date:
            no = re.search(re.escape(path) + r"/(\d+)", a["href"]).group(1)
            out.append((no, " ".join(a.get_text(" ", strip=True).split()), date.group()))
    return out


def parse_detail(html: str) -> tuple[str, str, list[Attachment]]:
    """(등록일, 본문, 첨부)."""
    s = BeautifulSoup(html, "html.parser")
    info = s.select_one(".tbl_info")
    date = DATE.search(info.get_text(" ")) if info else None
    con = s.select_one(".view_con")
    body = " ".join(con.get_text(" ", strip=True).split()) if con else ""
    names = [" ".join(sp.get_text(" ", strip=True).split()) for sp in s.select(".view_file .fileBr > span")]
    urls = list(dict.fromkeys(FILE_URL.findall(html)))
    if len(names) != len(urls):  # 짝이 안 맞으면 주소의 파일명(확장자 포함)을 쓴다
        names = [u.rsplit("/", 1)[-1] for u in urls]
    return (date.group() if date else ""), body, [Attachment(n, u) for n, u in zip(names, urls)]


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, path in BOARDS:
        for page in range(1, MAX_PAGES + 1):
            res = http.get(f"{BASE}{path}", params={"page": page})
            res.raise_for_status()
            rows = parse_list(res.text, path)
            for no, title, date in rows:
                if date < since.isoformat():
                    continue
                url = f"{BASE}{path}/{no}"
                d = http.get(url)
                d.raise_for_status()
                posted, body, atts = parse_detail(d.text)
                out.append(Post("KOSAC", kind, no, title, posted or date, url, body=body,
                                attachments=pick_attachments(atts)))
            if not rows or min(r[2] for r in rows) < since.isoformat():
                break
    return out
