"""수집 진입점.

  python -m harvest.collect --dry-run            # 수집 결과를 로그로만 출력
  python -m harvest.collect --send               # 승인 시트로 보낸다(분류 전 단계에서는 쓰지 않는다)

지금 구현된 수집기: MSIT(과기정통부 API)
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

from . import sheet
from .sources import msit
from .sources.base import Http, Post

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {"MSIT": msit.collect}
KST = datetime.timezone(datetime.timedelta(hours=9))


def load_agencies() -> dict[str, dict]:
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    return {a["id"]: a for a in cfg["agencies"]}


def doc_name_from_title(title: str) -> str:
    """문서명 초안: 괄호 머리말·끝 설명을 걷어낸다. 분류 단계에서 LLM이 다시 제안한다."""
    t = re.sub(r"^\s*[\[\(（【<〈][^\]\)）】>〉]{1,15}[\]\)）】>〉]\s*", "", title)
    t = re.sub(r"[「」『』\"'“”‘’]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:60]


def to_rows(posts: list[Post], agencies: dict[str, dict], now: datetime.datetime) -> list[dict]:
    rows = []
    for p in posts:
        a = agencies[p.agency]
        for att in p.attachments:
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
                "recommend": "검토 필요",
                "doc_name": doc_name_from_title(p.title),
                "year": p.posted_at[:4],
            })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="수집기 id 하나만(예: MSIT)")
    ap.add_argument("--pages", type=int, default=1)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send", action="store_true")
    args = ap.parse_args(argv)

    agencies = load_agencies()
    now = datetime.datetime.now(KST)
    http = Http()
    posts: list[Post] = []
    failed = []
    for sid, fn in SOURCES.items():
        if args.only and sid != args.only:
            continue
        try:
            got = fn(http, pages=args.pages)
            print(f"[{sid}] 게시글 {len(got)}건")
            posts += got
        except Exception as e:  # 한 기관이 실패해도 나머지는 계속
            failed.append(sid)
            print(f"[{sid}] 실패: {e}")

    rows = to_rows(posts, agencies, now)
    no_att = sum(1 for p in posts if not p.attachments)
    print(f"시트 행 {len(rows)}개 (첨부 없는 글 {no_att}건은 제외)")
    for p in posts:
        exts = ",".join(a.ext or "?" for a in p.attachments) or "-"
        print(f"  {p.posted_at} [{p.kind}] {p.title[:50]}  첨부:{exts}")

    if args.send and rows:
        print("시트 전송:", sheet.post_rows(rows))
    return 1 if failed and not posts else 0


if __name__ == "__main__":
    sys.exit(main())
