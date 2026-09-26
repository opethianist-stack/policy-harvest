"""1단계 사전 조사: 기관 사이트 접속성·게시판 구조·robots.txt 확인.

GitHub Actions 러너에서 실행해 결과를 out/probe.json, out/probe.md로 남긴다.
"""

from __future__ import annotations

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import urllib3
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 20
DELAY = 1.0
MAX_CANDIDATES = 10

DATE_RE = re.compile(r"20\d{2}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,2}")
ATTACH_RE = re.compile(r"\.(hwp|hwpx|pdf|docx?|xlsx?|zip)\b|download|fileDown|atchFile", re.I)
JS_MARKERS = {
    "next": "__NEXT_DATA__",
    "nuxt": "__NUXT__",
    "vue": "data-v-",
    "react-root": 'id="root"',
    "vue-app": 'id="app"',
    "angular": "ng-app",
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})


@dataclass
class Fetch:
    url: str
    status: int | None = None
    elapsed_ms: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    bytes: int | None = None
    error: str | None = None
    ssl_fallback: bool = False  # 인증서 검증 실패 후 verify=False로 받은 경우


@dataclass
class PageShape:
    table_rows: int = 0
    list_items: int = 0
    date_count: int = 0
    script_tags: int = 0
    text_chars: int = 0
    js_markers: list[str] = field(default_factory=list)
    js_links: int = 0  # href="javascript:..." 또는 onclick 상세보기
    attach_links: int = 0
    verdict: str = ""


def fetch(url: str) -> tuple[Fetch, str | None]:
    f = Fetch(url=url)
    for verify in (True, False):
        t0 = time.monotonic()
        try:
            r = session.get(url, timeout=TIMEOUT, verify=verify, allow_redirects=True)
        except requests.exceptions.SSLError as e:
            if verify:
                f.error = f"SSLError: {e.__class__.__name__}"
                continue
            f.error = f"SSLError: {e}"
            return f, None
        except requests.RequestException as e:
            f.error = f"{e.__class__.__name__}: {str(e)[:200]}"
            return f, None
        f.elapsed_ms = int((time.monotonic() - t0) * 1000)
        f.status = r.status_code
        f.final_url = r.url
        f.content_type = r.headers.get("content-type")
        f.bytes = len(r.content)
        f.ssl_fallback = not verify
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return f, r.text
    return f, None


def shape_of(html: str) -> PageShape:
    soup = BeautifulSoup(html, "html.parser")
    s = PageShape()
    s.table_rows = len(soup.select("table tbody tr"))
    s.list_items = len(soup.select("ul li, ol li"))
    s.script_tags = len(soup.find_all("script"))
    body = soup.body or soup
    text = body.get_text(" ", strip=True)
    s.text_chars = len(text)
    s.date_count = len(DATE_RE.findall(text))
    s.js_markers = [k for k, m in JS_MARKERS.items() if m in html]
    s.js_links = sum(
        1
        for a in soup.find_all("a")
        if (a.get("href") or "").lower().startswith("javascript:") or a.get("onclick")
    )
    s.attach_links = sum(1 for a in soup.find_all("a", href=True) if ATTACH_RE.search(a["href"]))
    if s.date_count >= 5 and (s.table_rows or s.list_items):
        s.verdict = "정적 목록(서버 렌더링)"
    elif s.js_markers or (s.script_tags > 10 and s.text_chars < 1500):
        s.verdict = "JS 렌더링 의심"
    else:
        s.verdict = "판단 보류(수동 확인)"
    return s


def find_candidates(home_url: str, html: str, keywords: dict[str, list[str]]) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(home_url).netloc.replace("www.", "")
    seen: set[str] = set()
    out: list[dict] = []
    for a in soup.find_all("a"):
        label = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        if not label or href.startswith(("#", "javascript:", "mailto:")):
            continue
        kind = next((k for k, words in keywords.items() if any(w in label for w in words)), None)
        if not kind:
            continue
        url = urljoin(home_url, href)
        if host not in urlparse(url).netloc or url in seen:
            continue
        seen.add(url)
        out.append({"kind": kind, "label": label[:40], "url": url})
    # 종류별로 고르게 남긴다
    out.sort(key=lambda c: list(keywords).index(c["kind"]))
    picked: list[dict] = []
    per_kind: dict[str, int] = {}
    for c in out:
        if per_kind.get(c["kind"], 0) < 3 and len(picked) < MAX_CANDIDATES:
            picked.append(c)
            per_kind[c["kind"]] = per_kind.get(c["kind"], 0) + 1
    return picked


def robots(home_url: str) -> tuple[dict, RobotFileParser | None]:
    url = urljoin(home_url, "/robots.txt")
    f, text = fetch(url)
    info = {"fetch": asdict(f), "text": (text or "")[:2000]}
    if f.status == 200 and text is not None:
        rp = RobotFileParser()
        rp.parse(text.splitlines())
        return info, rp
    return info, None


def probe_agency(a: dict, keywords: dict[str, list[str]]) -> dict:
    res: dict = {"id": a["id"], "name": a["name"], "ministry": a.get("ministry")}
    r_info, rp = robots(a["home"])
    res["robots"] = r_info
    time.sleep(DELAY)

    home_f, home_html = fetch(a["home"])
    res["home"] = asdict(home_f)
    if home_html:
        res["home_shape"] = asdict(shape_of(home_html))

    boards = [{"kind": k, "label": "config", "url": u} for k, u in (a.get("board_urls") or {}).items()]
    if not boards and home_html:
        boards = find_candidates(home_f.final_url or a["home"], home_html, keywords)

    res["boards"] = []
    for b in boards:
        time.sleep(DELAY)
        f, html = fetch(b["url"])
        entry = {**b, "fetch": asdict(f)}
        if rp:
            entry["robots_allowed"] = rp.can_fetch("*", b["url"])
        if html:
            entry["shape"] = asdict(shape_of(html))
        res["boards"].append(entry)
    return res


def probe_rss(url: str) -> dict:
    f, text = fetch(url)
    res: dict = {"fetch": asdict(f)}
    if not text:
        return res
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        res["error"] = f"ParseError: {e}"
        return res
    items = root.findall(".//item")
    res["item_count"] = len(items)
    sample = []
    for it in items[:30]:
        row = {c.tag.split("}")[-1]: (c.text or "").strip()[:120] for c in it}
        sample.append({k: row.get(k) for k in ("title", "link", "author", "creator", "category", "pubDate") if row.get(k)})
    res["sample"] = sample
    res["fields"] = sorted({c.tag.split("}")[-1] for it in items for c in it})
    return res


def probe_aggregator(g: dict) -> dict:
    res: dict = {"id": g["id"], "name": g["name"]}
    r_info, _ = robots(g["home"])
    res["robots"] = r_info
    time.sleep(DELAY)
    f, html = fetch(g["home"])
    res["home"] = asdict(f)
    if html:
        res["home_shape"] = asdict(shape_of(html))
    if g.get("rss"):
        time.sleep(DELAY)
        res["rss"] = probe_rss(g["rss"])
    return res


def fmt_fetch(f: dict) -> str:
    if f.get("error") and not f.get("status"):
        return f"실패 ({f['error']})"
    s = f"{f['status']} / {f['elapsed_ms']}ms"
    if f.get("ssl_fallback"):
        s += " / 인증서 검증 실패"
    return s


def to_markdown(data: dict) -> str:
    L = ["# 기관 사이트 접속 조사", "", f"- 실행 시각(UTC): {data['run_at']}", ""]
    L += ["## 기관별 요약", "", "| 기관 | 홈 | robots.txt | 홈 구조 |", "|---|---|---|---|"]
    for a in data["agencies"]:
        shape = a.get("home_shape", {}).get("verdict", "-")
        L.append(f"| {a['id']} | {fmt_fetch(a['home'])} | {fmt_fetch(a['robots']['fetch'])} | {shape} |")
    for a in data["agencies"]:
        L += ["", f"### {a['id']} {a['name']}", ""]
        if not a["boards"]:
            L.append("- 게시판 후보를 찾지 못함")
            continue
        L += ["| 종류 | 링크 텍스트 | 응답 | robots | 판정 | 표행/날짜/JS링크/첨부 | URL |", "|---|---|---|---|---|---|---|"]
        for b in a["boards"]:
            sh = b.get("shape") or {}
            nums = f"{sh.get('table_rows', '-')}/{sh.get('date_count', '-')}/{sh.get('js_links', '-')}/{sh.get('attach_links', '-')}"
            allowed = {True: "허용", False: "차단"}.get(b.get("robots_allowed"), "-")
            L.append(
                f"| {b['kind']} | {b['label']} | {fmt_fetch(b['fetch'])} | {allowed} | {sh.get('verdict', '-')} | {nums} | {b['url']} |"
            )
        robots_text = a["robots"]["text"].strip()
        if robots_text:
            L += ["", "<details><summary>robots.txt</summary>", "", "```", robots_text[:1500], "```", "</details>"]
    L += ["", "## 집계 경로", ""]
    for g in data["aggregators"]:
        L.append(f"- {g['id']} {g['name']}: 홈 {fmt_fetch(g['home'])}, robots {fmt_fetch(g['robots']['fetch'])}")
        rss = g.get("rss")
        if rss:
            L.append(f"  - RSS: {fmt_fetch(rss['fetch'])}, 항목 {rss.get('item_count', '-')}개, 필드 {rss.get('fields', '-')}")
            for s in rss.get("sample", [])[:15]:
                L.append(f"    - {s.get('title', '')} | {s.get('author') or s.get('creator') or s.get('category') or ''}")
    return "\n".join(L) + "\n"


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    data = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agencies": [probe_agency(a, cfg["board_keywords"]) for a in cfg["agencies"]],
        "aggregators": [probe_aggregator(g) for g in cfg.get("aggregators", [])],
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "probe.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(data)
    (OUT / "probe.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
