"""시도교육청 주요업무계획(연 1회).

sources.yaml 의 교육청 항목 중 `plan` 설정이 있는 곳만 받는다(manual·robots_blocked·skip_upload 제외).
글 하나 = 교육청의 그해 계획 문서. 글 키는 `{id}:plan:{연도}`라 시트에 한 번 들어가면 다시 오지 않는다.
대상 연도: 12월에는 다음 해, 그 밖에는 올해(계획은 전년 12월~그해 3월에 올라온다).

plan 설정
  url        계획이 있는 페이지
  doc_name   파일명에 쓸 문서명(교육청이 붙인 이름에서 연도를 뺀 것)
  file       파일 주소를 바로 적는 경우(페이지에서 찾지 않는다). 해마다 바뀌므로 연도 키로 적는다: {2026: "https://…"}
  link       고를 링크 글자(정규식)
  href       고를 링크 주소(정규식)
  near       링크를 감싼 행(li·tr)에 있어야 할 글자. {year}는 대상 연도로 바뀐다
  page_year  페이지 본문에 대상 연도가 있어야 한다(연도가 주소·제목에 드러나지 않는 페이지)
  js         href가 javascript 함수면 인자를 꺼낼 정규식, js_url 은 {0} 자리에 인자를 넣은 다운로드 주소
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from .base import Attachment, Http, Post

ROOT = Path(__file__).resolve().parents[2]


def target_year(today: datetime.date) -> int:
    return today.year + 1 if today.month == 12 else today.year


def offices() -> list[dict]:
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    return [a for a in cfg["agencies"] if a.get("category") == "교육청" and a.get("plan")
            and not (a.get("manual") or a.get("robots_blocked") or a.get("skip_upload"))]


def find_link(html: str, base: str, plan: dict, year: int) -> str | None:
    """설정에 맞는 첫 다운로드 주소. 없으면 None."""
    s = BeautifulSoup(html, "html.parser")
    if plan.get("page_year") and str(year) not in s.get_text(" "):
        return None
    near = plan.get("near", "").replace("{year}", str(year))
    for a in s.find_all("a"):
        href = (a.get("href") or "").strip()
        text = " ".join(a.get_text(" ", strip=True).split())
        if plan.get("link") and not re.search(plan["link"], text):
            continue
        if plan.get("href") and not re.search(plan["href"], href):
            continue
        if near:
            box = a.find_parent(["li", "tr"])
            if not box or not re.search(near, " ".join(box.get_text(" ", strip=True).split())):
                continue
        if plan.get("js"):
            m = re.search(plan["js"], href)
            if not m:
                continue
            href = plan["js_url"].format(*m.groups())
        return urljoin(base, href)
    return None


def collect(http: Http, since: datetime.date, today: datetime.date) -> list[Post]:
    year = target_year(today)
    out, missing = [], []
    for o in offices():
        plan = o["plan"]
        url = (plan.get("file") or {}).get(year)
        page = plan.get("url") or url
        if not url:
            res = http.get(plan["url"])
            res.raise_for_status()
            url = find_link(res.text, res.url, plan, year)
        if not url:
            missing.append(o["id"])
            continue
        out.append(Post(o["id"], "plan", str(year), f"{year} {plan['doc_name']}", f"{year}-01-01", page,
                        attachments=[Attachment(f"{plan['doc_name']}.{plan.get('ext', 'pdf')}", url)]))
    if missing:
        print(f"  [EDU] {year}년 계획을 찾지 못한 교육청: {', '.join(missing)} (아직 안 올라왔거나 페이지가 바뀜)")
    return out


def result(agency: dict, year: str) -> dict:
    """교육청 계획은 분류하지 않는다(모두 포함)."""
    return {"recommend": "포함", "doc_type": "업무계획", "topics": [], "doc_name": agency["plan"]["doc_name"],
            "year": year, "reason": "시도교육청 연간 주요업무계획", "attachments": []}
