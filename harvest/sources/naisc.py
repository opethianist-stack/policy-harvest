"""국가인공지능전략위원회(NAISC, www.aikorea.go.kr): 보도자료·정책자료.

게시판 주소가 JSON을 돌려준다.
  목록 /web/board/brdList.do?menu_cd={메뉴}&currentPage=N → brdList[{num, title, write_dt, att_file}]
  상세 /web/board/brdDetail.do?menu_cd=&num= → brd{cont(HTML)}, fileList[{file_org, file_save, subpath}]
  첨부 /attach/cms/board/{subpath}/{file_save}
메뉴: 000012 보도자료, 000011 정책자료(행동계획 원문 등). 000014(인터뷰·기고)는 언론 기사라 받지 않는다
"""

from __future__ import annotations

import datetime

from bs4 import BeautifulSoup

from .base import Attachment, Http, Post, pick_attachments

BASE = "https://www.aikorea.go.kr"
BOARDS = [("press", "000012"), ("policy", "000011")]
MAX_PAGES = 3


def parse_list(data: dict) -> list[tuple[str, str, str]]:
    return [(str(it["num"]), " ".join(str(it.get("title") or "").split()), str(it.get("write_dt") or "")[:10])
            for it in data.get("brdList") or []]


def parse_detail(data: dict) -> tuple[str, list[Attachment]]:
    cont = (data.get("brd") or {}).get("cont") or ""
    body = " ".join(BeautifulSoup(cont, "html.parser").get_text(" ", strip=True).split())
    atts = [Attachment(f["file_org"], f"{BASE}/attach/cms/board/{f['subpath']}/{f['file_save']}")
            for f in data.get("fileList") or [] if f.get("file_save") and f.get("subpath")]
    return body, atts


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    out = []
    for kind, menu in BOARDS:
        seen = set()
        for page in range(1, MAX_PAGES + 1):
            res = http.get(f"{BASE}/web/board/brdList.do", params={"menu_cd": menu, "currentPage": page})
            res.raise_for_status()
            rows = [r for r in parse_list(res.json()) if r[0] not in seen]
            for no, title, date in rows:
                seen.add(no)
                if date < since.isoformat():
                    continue
                url = f"{BASE}/web/board/brdDetail.do?menu_cd={menu}&num={no}"
                d = http.get(url)
                d.raise_for_status()
                body, atts = parse_detail(d.json())
                out.append(Post("NAISC", kind, no, title, date, url, body=body, attachments=pick_attachments(atts)))
            # 정책자료는 날짜순이 아닐 수 있어(행동계획 등 고정 자료) 한 쪽이 모두 기간 밖일 때 멈춘다
            if not rows or max(r[2] for r in rows) < since.isoformat():
                break
    return out
