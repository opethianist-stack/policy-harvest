"""새 수집기를 만들 때 쓰는 페이지 구조 확인 도구(dry-run 워크플로에서 실행).

  python scripts/peek.py URL [--follow 정규식] [--grep 정규식]

목록 페이지의 표 행, 정규식에 맞는 링크, 첨부로 보이는 링크를 출력한다.
--follow 를 주면 정규식에 맞는 첫 링크(상세 페이지)도 받아 같은 방식으로 출력한다.
"""

from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = "policy-harvest/0.1 (+https://github.com/opethianist-stack/policy-harvest)"
FILE_HINT = re.compile(r"down|file|atch|attach|\.(pdf|hwpx?|zip|xlsx?|odt)\b", re.I)


def show(url: str, follow: str | None, grep: str | None = None, depth: int = 0) -> None:
    print(f"\n===== {url}")
    try:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except requests.exceptions.SSLError:
            print("(인증서 검증 실패, 검증 없이 다시 받음)")
            requests.packages.urllib3.disable_warnings()
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30, verify=False)
    except requests.RequestException as e:
        print("요청 실패:", e)
        return
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    print("HTTP", r.status_code, r.headers.get("content-type"), len(r.text), "자")
    s = BeautifulSoup(r.text, "html.parser")
    print("title:", s.title.get_text(strip=True) if s.title else None)
    for ti, t in enumerate(s.find_all("table")[:3]):
        print(f"-- table[{ti}] class={t.get('class')}")
        for tr in t.find_all("tr")[:6]:
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))[:50] for c in tr.find_all(["th", "td"])]
            print("   ", cells)
    links = [(a.get("href") or "", a.get("onclick") or "", re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:70])
             for a in s.find_all("a")]
    if follow:
        hits = [l for l in links if re.search(follow, l[0])]
        print(f"-- links matching {follow!r}: {len(hits)}")
        for h in hits[:12]:
            print("   ", h)
    files = [l for l in links if FILE_HINT.search(l[0] + " " + l[1])]
    print(f"-- file-like links: {len(files)}")
    for f in files[:12]:
        print("   ", f)
    # 게시일로 보이는 날짜
    dates = sorted(set(re.findall(r"20\d\d[.-]\d\d[.-]\d\d", s.get_text(" "))))[-5:]
    print("-- dates:", dates)
    if not s.find("table"):
        print("-- body text head:", re.sub(r"\s+", " ", s.get_text(" ", strip=True))[:1200])
    if grep:
        for m in list(re.finditer(grep, r.text))[:15]:
            print("   grep:", repr(r.text[max(0, m.start() - 150): m.end() + 250]))
    if follow and depth == 0:
        hits = [l for l in links if re.search(follow, l[0])]
        if hits:
            show(urljoin(url, hits[0][0]), None, grep, depth + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--follow")
    ap.add_argument("--grep", help="원문 HTML에서 찾아 앞뒤를 출력할 정규식")
    a = ap.parse_args()
    show(a.url, a.follow, a.grep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
