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
HTML_DIR = OUT / "html"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 20
DELAY = 1.0
MAX_CANDIDATES = 10
MAX_FEEDS = 15
SITEMAP_WORDS = ("사이트맵", "sitemap", "전체메뉴")
JS_REDIRECT_RE = re.compile(
    r"""(?:window\.|document\.|top\.|self\.)?location(?:\.href)?\s*(?:=|\.replace\(|\.assign\()\s*['"]([^'"]+)['"]"""
)

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


def dump_html(name: str, html: str) -> str:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    path = HTML_DIR / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(OUT))


def classify(label: str, keywords: dict[str, list[str]]) -> str | None:
    return next((k for k, words in keywords.items() if any(w in label for w in words)), None)


def link_inventory(base: str, html: str, keywords: dict[str, list[str]]) -> dict:
    """메뉴 구조 파악용: 링크 수, 키워드 링크(JS 링크 포함), 원문 속 키워드 빈도, 프레임·리다이렉트."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a")
    kw_links = []
    js_count = 0
    sitemap = None
    for a in anchors:
        label = a.get_text(" ", strip=True)
        href = (a.get("href") or "").strip()
        onclick = a.get("onclick") or ""
        is_js = href.lower().startswith("javascript:") or bool(onclick)
        js_count += is_js
        if not sitemap and any(w in label.lower() or w in href.lower() for w in SITEMAP_WORDS) and not is_js:
            sitemap = urljoin(base, href)
        kind = classify(label, keywords)
        if kind:
            kw_links.append({"kind": kind, "label": label[:40], "href": href[:200], "onclick": onclick[:200]})
    refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    refresh_url = None
    if refresh and "url=" in (refresh.get("content") or "").lower():
        refresh_url = urljoin(base, refresh["content"].split("=", 1)[1].strip(" '\""))
    frames = [urljoin(base, f["src"]) for f in soup.find_all(["frame", "iframe"], src=True)]
    m = JS_REDIRECT_RE.search(html)
    js_redirect = urljoin(base, m.group(1)) if m else None
    raw_hits = {k: sum(html.count(w) for w in words) for k, words in keywords.items()}
    return {
        "anchors": len(anchors),
        "js_anchors": js_count,
        "keyword_links": kw_links[:40],
        "raw_keyword_hits": raw_hits,
        "sitemap": sitemap,
        "meta_refresh": refresh_url,
        "js_redirect": js_redirect,
        "html_head": html[:800] if len(anchors) < 5 else "",
        "frames": frames[:5],
    }


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


def resolve_home(a: dict) -> tuple[list[dict], Fetch | None, str | None]:
    """home, alt_homes 순서로 시도해 처음 200을 준 주소를 쓴다."""
    attempts = []
    for url in [a["home"], *(a.get("alt_homes") or [])]:
        f, html = fetch(url)
        attempts.append(asdict(f))
        if f.status == 200 and html:
            return attempts, f, html
        time.sleep(DELAY)
    return attempts, None, None


def probe_agency(a: dict, keywords: dict[str, list[str]]) -> dict:
    res: dict = {"id": a["id"], "name": a["name"], "ministry": a.get("ministry")}
    attempts, home_f, home_html = resolve_home(a)
    res["home_attempts"] = attempts
    res["home"] = asdict(home_f) if home_f else attempts[0]
    if not home_f or not home_html:
        res["robots"] = {"fetch": {"url": "-", "error": "홈 접속 실패로 생략"}, "text": ""}
        res["boards"] = []
        return res
    base = home_f.final_url or home_f.url
    res["home_dump"] = dump_html(f"{a['id']}_home", home_html)
    inv = link_inventory(base, home_html, keywords)

    # 링크가 거의 없고 프레임·meta refresh만 있는 홈이면 실제 첫 화면을 따라간다
    nxt = inv["meta_refresh"] or inv["js_redirect"] or (inv["frames"][0] if inv["frames"] else None)
    if nxt and inv["anchors"] < 10:
        time.sleep(DELAY)
        f2, html2 = fetch(nxt)
        res["home_followed"] = asdict(f2)
        if html2:
            base, home_html = f2.final_url or nxt, html2
            res["home_dump_followed"] = dump_html(f"{a['id']}_home_followed", html2)
            inv = link_inventory(base, home_html, keywords)
    res["home_shape"] = asdict(shape_of(home_html))
    res["home_links"] = inv

    time.sleep(DELAY)
    r_info, rp = robots(base)
    res["robots"] = r_info

    pages = [(base, home_html)]
    if inv["sitemap"]:
        time.sleep(DELAY)
        f3, html3 = fetch(inv["sitemap"])
        res["sitemap"] = asdict(f3)
        if html3:
            res["sitemap_dump"] = dump_html(f"{a['id']}_sitemap", html3)
            res["sitemap_links"] = link_inventory(f3.final_url or inv["sitemap"], html3, keywords)
            pages.append((f3.final_url or inv["sitemap"], html3))

    boards = [{"kind": b["kind"], "label": b.get("source", "config"), "url": b["url"]} for b in a.get("boards") or []]
    if not boards:
        seen: set[str] = set()
        for page_url, page_html in pages:
            for c in find_candidates(page_url, page_html, keywords):
                if c["url"] not in seen and len(boards) < MAX_CANDIDATES:
                    seen.add(c["url"])
                    boards.append(c)

    res["boards"] = []
    for b in boards:
        time.sleep(DELAY)
        f, html = fetch(b["url"])
        entry = {**b, "fetch": asdict(f)}
        if rp:
            entry["robots_allowed"] = rp.can_fetch("*", b["url"])
        if html:
            entry["shape"] = asdict(shape_of(html))
            entry["dump"] = dump_html(f"{a['id']}_board_{len(res['boards'])}", html)
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


def discover_feeds(base: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = [urljoin(base, l["href"]) for l in soup.find_all("link", href=True) if "rss" in (l.get("type") or "")]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".xml") or "/rss/" in href.lower():
            urls.append(urljoin(base, href))
    return list(dict.fromkeys(urls))


def probe_aggregator(g: dict) -> dict:
    res: dict = {"id": g["id"], "name": g["name"]}
    r_info, _ = robots(g["home"])
    res["robots"] = r_info
    time.sleep(DELAY)
    f, html = fetch(g["home"])
    res["home"] = asdict(f)
    feeds: list[str] = list(g.get("rss") or [])
    if html:
        res["home_shape"] = asdict(shape_of(html))
        res["home_dump"] = dump_html(f"{g['id']}_home", html)
        feeds += discover_feeds(f.final_url or g["home"], html)
    res["rss_index"] = []
    for idx in g.get("rss_index") or []:
        time.sleep(DELAY)
        fi, hi = fetch(idx)
        entry = asdict(fi)
        if hi:
            soup = BeautifulSoup(hi, "html.parser")
            entry["rss_links"] = [
                {"text": a.get_text(" ", strip=True)[:40], "href": (a.get("href") or "")[:200], "onclick": (a.get("onclick") or "")[:200]}
                for a in soup.find_all("a")
                if re.search(r"rss|xml", (a.get("href") or "") + (a.get("onclick") or "") + a.get_text(), re.I)
            ][:40]
        res["rss_index"].append(entry)
        if hi:
            dump_html(f"{g['id']}_rss_index", hi)
            feeds += discover_feeds(fi.final_url or idx, hi)
    feeds = list(dict.fromkeys(feeds))
    res["feeds_found"] = feeds
    res["feeds"] = []
    for url in feeds[:MAX_FEEDS]:
        time.sleep(DELAY)
        res["feeds"].append({"url": url, **probe_rss(url)})
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
        if len(a.get("home_attempts", [])) > 1:
            L.append("- 홈 주소 시도: " + ", ".join(f"{t['url']} → {fmt_fetch(t)}" for t in a["home_attempts"]))
        inv = a.get("home_links")
        if inv:
            used = (a.get("home_followed") or a["home"]).get("final_url")
            L.append(f"- 사용한 홈: {used} (저장: {a.get('home_dump_followed') or a.get('home_dump')})")
            L.append(f"- 링크 {inv['anchors']}개, 그중 JS 링크 {inv['js_anchors']}개, 프레임 {len(inv['frames'])}개")
            L.append(f"- HTML 원문 속 키워드 빈도: {inv['raw_keyword_hits']}")
            if a.get("home_followed"):
                L.append(f"- 첫 화면 이동: {a['home']['final_url']} → {fmt_fetch(a['home_followed'])} ({a['home_followed']['url']})")
            if inv["html_head"]:
                L += ["- 홈 HTML 앞부분 (링크가 거의 없어 원문 확인용):", "", "```html", inv["html_head"], "```", ""]
            sm = a.get("sitemap")
            L.append(f"- 사이트맵: {inv['sitemap'] or '링크 없음'}" + (f" → {fmt_fetch(sm)}" if sm else ""))
            kls = inv["keyword_links"] + (a.get("sitemap_links") or {}).get("keyword_links", [])
            if kls:
                L.append("- 키워드 링크:")
                for k in kls[:15]:
                    L.append(f"  - [{k['kind']}] {k['label']} | href=`{k['href'][:100]}`" + (f" onclick=`{k['onclick'][:80]}`" if k["onclick"] else ""))
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
        for idx in g.get("rss_index", []):
            L.append(f"  - RSS 목록 페이지: {idx['url']} → {fmt_fetch(idx)}, rss/xml 관련 링크 {len(idx.get('rss_links', []))}개")
            for rl in idx.get("rss_links", [])[:25]:
                L.append(f"    - {rl['text']} | href=`{rl['href'][:120]}`" + (f" onclick=`{rl['onclick'][:80]}`" if rl["onclick"] else ""))
        if g.get("feeds_found") is not None:
            L.append(f"  - 찾은 피드 {len(g['feeds_found'])}개 (앞 {MAX_FEEDS}개 확인)")
        for rss in g.get("feeds", []):
            L.append(f"  - {rss['url']}: {fmt_fetch(rss['fetch'])}, 항목 {rss.get('item_count', '-')}개, 필드 {rss.get('fields', '-')}")
            for s in rss.get("sample", [])[:10]:
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
