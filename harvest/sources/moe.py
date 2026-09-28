"""교육부(MOE): 보도자료 게시판 + 올해 업무계획 페이지.

보도자료 목록 /boardCnts/listRenew.do?boardID=294&m=020402&s=moe&page=N
  표 행: a onclick="goView('294','{boardSeq}',…)" title=제목, 등록일 YYYY-MM-DD
상세 /boardCnts/viewRenew.do?boardID=294&boardSeq=&lev=0&m=020402&s=moe&opType=N
  본문 .midd, 첨부 .atta-inner 안 a[href*=fileDown.do] ("파일명 [ 156.2 KB ] 다운로드 미리보기")
업무계획 /sub/infoRenew.do?page=72762&m=031101&s=moe (제목 "2026년 업무계획")
  /upload/filedown/{연도}_business_plan_data.pdf|hwp, _press_release.pdf|hwpx 를 바로 링크한다. 연 1회 글 하나로 다룬다
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, collect_board, pick_attachments

BASE = "https://www.moe.go.kr"
PRESS = ("294", "020402")  # (boardID, m)
PLAN_URL = f"{BASE}/sub/infoRenew.do?page=72762&m=031101&s=moe"
DATE = re.compile(r"20\d\d-\d\d-\d\d")
SIZE = re.compile(r"\s*\[\s*[\d.,]+\s*[KMG]?B\s*\].*$")


def parse_list(html: str) -> list[tuple[str, str, str]]:
    s = BeautifulSoup(html, "html.parser")
    out = []
    for a in s.find_all("a", onclick=re.compile(r"goView\('\d+',\s*'\d+'")):
        no = re.search(r"goView\('\d+',\s*'(\d+)'", a["onclick"]).group(1)
        row = a.find_parent("tr")
        date = DATE.search(row.get_text(" ") if row else "")
        title = (a.get("title") or "").strip() or " ".join(a.get_text(" ", strip=True).split())
        if date:
            out.append((no, title, date.group()))
    return out


def parse_detail(html: str, url: str) -> tuple[str, list[Attachment]]:
    s = BeautifulSoup(html, "html.parser")
    con = s.select_one(".midd")
    body = " ".join(con.get_text(" ", strip=True).split()) if con else ""
    atts, seen = [], set()
    for a in s.find_all("a", href=re.compile(r"fileDown\.do")):
        href = urljoin(url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        box = a.find_parent("li") or a.parent
        name = SIZE.sub("", " ".join(box.get_text(" ", strip=True).split())).strip()
        atts.append(Attachment(name, href))
    return body, atts


def parse_plan(html: str, year: int) -> list[Attachment]:
    """올해 업무계획 페이지의 파일 링크. 제목에 대상 연도가 없으면 빈 목록."""
    s = BeautifulSoup(html, "html.parser")
    if f"{year}년" not in (s.title.get_text() if s.title else ""):
        return []
    atts = []
    for a in s.find_all("a", href=re.compile(rf"/upload/filedown/{year}_[\w.-]+\.(pdf|hwpx?)$")):
        href = urljoin(PLAN_URL, a["href"])
        atts.append(Attachment(href.rsplit("/", 1)[1], href))
    return atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    board, m = PRESS
    out = collect_board(
        http, "MOE", "press", f"{BASE}/boardCnts/listRenew.do",
        lambda page: {"boardID": board, "m": m, "s": "moe", "page": page},
        parse_list,
        lambda no: f"{BASE}/boardCnts/viewRenew.do?boardID={board}&boardSeq={no}&lev=0&m={m}&s=moe&opType=N",
        parse_detail, since)
    res = http.get(PLAN_URL)
    res.raise_for_status()
    atts = parse_plan(res.text, today.year)
    if atts:
        out.append(Post("MOE", "policy", f"plan{today.year}", f"{today.year}년 교육부 업무계획", f"{today.year}-01-01",
                        PLAN_URL, attachments=pick_attachments(atts)))
    return out
