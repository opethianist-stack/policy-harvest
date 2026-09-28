"""수집 진입점.

  python -m harvest.collect --dry-run                    # 수집 결과만 출력
  python -m harvest.collect --dry-run --classify --limit 5   # 새 글 5건만 분류해 출력
  python -m harvest.collect --send --classify            # 새 글을 분류해 승인 시트로 보낸다

지금 구현된 수집기: MSIT(과기정통부 API), NIPA·KOSAC(보도자료), NIA·KERIS(보도자료·공지사항), MOE·MOEL·NAISC(보도자료·정책자료), EDU(시도교육청 주요업무계획)
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

from . import sheet
from .classify import shorten
from .sources import edu, keris, kosac, moe, moel, msit, naisc, nia, nipa
from .sources.base import Http, Post

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {"MSIT": msit.collect, "MOE": moe.collect, "MOEL": moel.collect, "NAISC": naisc.collect, "NIPA": nipa.collect, "KOSAC": kosac.collect,
           "NIA": nia.collect, "KERIS": keris.collect, "EDU": edu.collect}
KST = datetime.timezone(datetime.timedelta(hours=9))


def load_agencies() -> dict[str, dict]:
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    return {a["id"]: a for a in cfg["agencies"]}


def doc_name_from_title(title: str) -> str:
    """분류 전 문서명 초안: 괄호 머리말·따옴표를 걷어낸다."""
    t = re.sub(r"^\s*[\[\(（【<〈][^\]\)）】>〉]{1,15}[\]\)）】>〉]\s*", "", title)
    t = re.sub(r"[「」『』｢｣\"'“”‘’]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:60]


# 실제 다운로드는 Apps Script(UrlFetchApp)가 한다. 일부 교육청은 User-Agent에 Mozilla가 없으면 빈 파일을 준다
APPS_SCRIPT_UA = "Mozilla/5.0 (compatible; Google-Apps-Script; beanserver; +https://script.google.com)"


def probe_file(http: Http, url: str, referer: str = "") -> str:
    """첨부 주소를 Apps Script와 같은 방식(User-Agent·Referer)으로 받아 상태·형식·크기·첫 바이트를 요약한다."""
    try:
        r = http.get(url, stream=True, timeout=60, headers={"User-Agent": APPS_SCRIPT_UA, "Referer": referer})
        head = next(r.iter_content(8), b"")
        size = r.headers.get("content-length", "?")
        r.close()
        return f"HTTP {r.status_code} {r.headers.get('content-type')} {size}B {head[:5]!r}"
    except Exception as e:  # 확인용이라 실패도 출력만 한다
        return f"실패 {e}"


def to_rows(posts: list[Post], agencies: dict[str, dict], now: datetime.datetime,
            results: dict[str, dict] | None = None) -> list[dict]:
    results = results or {}
    rows = []
    for p in posts:
        a = agencies[p.agency]
        r = results.get(p.key)
        per_att = {x["index"]: x for x in (r or {}).get("attachments", [])}
        for i, att in enumerate(p.attachments):
            x = per_att.get(i, {})
            rows.append({
                "collected_at": now.strftime("%Y-%m-%d %H:%M"),
                "post_key": p.key,
                "category": a["category"],
                "org": a["file_org"],
                "board": p.kind,
                "title": p.title,
                "post_url": p.url,
                "posted_at": p.posted_at,
                "att_name": att.name,
                "att_url": att.url,
                "recommend": r["recommend"] if r else "검토 필요",
                "doc_type": r["doc_type"] if r else "",
                "topics": r["topics"][:3] if r else [],
                "reason": r["reason"] if r else "",
                "doc_name": x.get("doc_name") or (r or {}).get("doc_name") or shorten(doc_name_from_title(p.title)),
                "kind": x.get("kind", ""),
                "year": (r or {}).get("year") or p.posted_at[:4],
                "file_no": str(a.get("file_no", "")),  # 시도교육청처럼 번호가 정해진 기관
            })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="수집기 id 하나만(예: MSIT)")
    ap.add_argument("--since-days", type=int, default=14, help="보도자료 수집 기간(일)")
    ap.add_argument("--classify", action="store_true", help="새 글을 Claude로 분류")
    ap.add_argument("--limit", type=int, default=0, help="분류할 새 글 수 상한(0이면 전부)")
    ap.add_argument("--probe-files", action="store_true", help="첨부를 실제로 받아 형식·크기를 확인(dry-run용)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send", action="store_true")
    args = ap.parse_args(argv)

    agencies = load_agencies()
    now = datetime.datetime.now(KST)
    since = now.date() - datetime.timedelta(days=args.since_days)
    http = Http()
    posts: list[Post] = []
    failed = []
    for sid, fn in SOURCES.items():
        if args.only and sid != args.only:
            continue
        try:
            got = fn(http, since=since, today=now.date())
            note = f", 주요정책 {now.year}년" if sid == "MSIT" else ""
            print(f"[{sid}] 게시글 {len(got)}건 (보도자료 {since} 이후{note})")
            posts += got
        except Exception as e:  # 한 기관이 실패해도 나머지는 계속
            failed.append(sid)
            print(f"[{sid}] 실패: {e}")

    no_att = [p for p in posts if not p.attachments]
    posts = [p for p in posts if p.attachments]
    if not sheet.missing_env():
        seen = sheet.existing_keys()
        before = len(posts)
        posts = [p for p in posts if p.key not in seen]
        print(f"시트에 이미 있는 글 {before - len(posts)}건 제외")
    print(f"새 글 {len(posts)}건 (첨부 없는 글 {len(no_att)}건 제외)")

    results: dict[str, dict] = {}
    if args.classify and posts:
        from . import classify
        client = classify.client()
        targets = posts[: args.limit] if args.limit else posts
        print(f"분류 {len(targets)}건 (모델 {classify.MODEL})")
        for p in targets:
            if p.kind != "plan":
                results[p.key] = classify.classify(client, p, agencies[p.agency])
        if args.limit:
            posts = targets

    for p in posts:  # 시도교육청 계획은 분류하지 않고 포함으로 둔다
        if p.kind == "plan":
            results[p.key] = edu.result(agencies[p.agency], p.post_id)

    for p in posts:
        r = results.get(p.key)
        tag = f"{r['recommend']}/{r['doc_type']}" if r else "-"
        print(f"  {p.posted_at} [{p.kind}] {p.title[:45]} | 첨부 {','.join(a.ext for a in p.attachments)} | {tag}")
        if r:
            print(f"      문서명: {r['doc_name']} ({r['year']}) · {r['reason']}")

    if args.probe_files:
        for p in posts:
            for att in p.attachments:
                print(f"  [파일] {p.agency} {att.name}: {probe_file(http, att.url, p.url)}")

    rows = to_rows(posts, agencies, now, results)
    print(f"시트 행 {len(rows)}개")
    if args.send and rows:
        print("시트 전송:", sheet.post_rows(rows))
    if failed:
        # 다른 기관 결과는 보낸 뒤 실패로 끝내 워크플로가 빨갛게 표시되게 한다(GitHub가 메일로 알린다)
        print("수집 실패 기관:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
