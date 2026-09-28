"""한국교육학술정보원(KERIS): 보도자료·공지사항.

목록 /main/na/ntt/selectNttList.do?mi={메뉴}&bbsId={게시판}&currPage=N
  표 행: a onclick="nttView('{nttSn}')", td.date 등록일 YYYY.MM.DD. 공지사항은 고정 글이 위에 붙는다
상세 /main/na/ntt/selectNttInfo.do?mi=&nttSn=&bbsId=
  본문 .view_cont, 첨부 a[href*=nttFileDownload.do] ("이름 (다운로드 : N회)"), 보도자료에 행사 사진(jpg)이 붙는다
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, collect_board, dotted_date

BASE = "https://www.keris.or.kr"
BOARDS = [("press", "1088", "1090"), ("notice", "1051", "1088")]  # (kind, mi, bbsId)


def parse_list(html: str) -> list[tuple[str, str, str]]:
    s = BeautifulSoup(html, "html.parser")
    out = []
    for a in s.find_all("a", onclick=re.compile(r"nttView\('\d+'\)")):
        no = re.search(r"nttView\('(\d+)'\)", a["onclick"]).group(1)
        row = a.find_parent("tr")
        td = row.select_one("td.date") if row else None
        date = dotted_date(td.get_text(" ") if td else (row or a).get_text(" "))
        if date:
            out.append((no, " ".join(a.get_text(" ", strip=True).split()), date))
    return out


def parse_detail(html: str, url: str) -> tuple[str, list[Attachment]]:
    s = BeautifulSoup(html, "html.parser")
    con = s.select_one(".view_cont")
    body = " ".join(con.get_text(" ", strip=True).split()) if con else ""
    atts, seen = [], set()
    for a in s.find_all("a", href=re.compile(r"nttFileDownload\.do")):
        href = urljoin(url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        name = re.sub(r"\s*\(다운로드\s*:\s*\d+회\)\s*$", "", " ".join(a.get_text(" ", strip=True).split()))
        atts.append(Attachment(name, href))
    return body, atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, mi, bbs in BOARDS:
        out += collect_board(
            http, "KERIS", kind, f"{BASE}/main/na/ntt/selectNttList.do",
            lambda page, mi=mi, bbs=bbs: {"mi": mi, "bbsId": bbs, "currPage": page},
            parse_list,
            lambda no, mi=mi, bbs=bbs: f"{BASE}/main/na/ntt/selectNttInfo.do?mi={mi}&nttSn={no}&bbsId={bbs}",
            parse_detail, since)
    return out
