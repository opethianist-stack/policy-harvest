"""한국과학창의재단(KOSAC): 보도자료 게시판.

Next.js 사이트지만 목록·상세 모두 서버에서 완성된 HTML이 온다.
목록 /menus/272/boards/394/posts?page=N → table.board_list 행: 번호, 구분, 제목(/posts/{글번호}?page=N), 첨부, 등록일(td.date), 조회
상세 /menus/272/boards/394/posts/{글번호}
  - 등록일: .tbl_info 의 "등록일 YYYY-MM-DD"
  - 첨부 이름: .view_file .fileBr span (다운로드 버튼 href는 비어 있고 스크립트가 연다)
  - 첨부 주소: 페이지에 실린 데이터(self.__next_f)의 fileUrl = https://cdn.kosac.re.kr/files/cms/attach/... (이름과 같은 순서).
    같은 CDN에 배너 이미지도 있어 cms/attach 경로만 쓴다
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
FILE_URL = re.compile(r"https://cdn\.kosac\.re\.kr/files/cms/attach/[^\"'\\\s<>]+")  # 배너 이미지(files/cms/banner 등)는 제외


def parse_list(html: str, path: str) -> list[tuple[str, str, str]]:
    """(글번호, 제목, 등록일) 목록."""
    s = BeautifulSoup(html, "html.parser")
    out = []
    for tr in s.select("table.board_list tr"):  # 서버 HTML에는 tbody가 없을 수 있다
        a = tr.find("a", href=re.compile(re.escape(path) + r"/\d+"))
        # 구분 칸도 class="date"(빈 template)라 날짜가 있는 칸을 찾는다
        date = next((m for td in tr.select("td.date") if (m := DATE.search(td.get_text()))), None)
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
    out, seen = [], set()
    for kind, path in BOARDS:
        # 기본 목록은 page=0(데이터의 "page":0)인데 링크에는 page=1이 붙는다. 번호 체계가 불분명해
        # 기본 목록 → page=1 → page=2 … 순으로 받고 이미 본 글은 건너뛴다
        for page in [None, *range(1, MAX_PAGES + 1)]:
            res = http.get(f"{BASE}{path}", params={} if page is None else {"page": page})
            res.raise_for_status()
            rows = [r for r in parse_list(res.text, path) if r[0] not in seen]
            for no, title, date in rows:
                seen.add(no)
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
