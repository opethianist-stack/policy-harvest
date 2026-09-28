"""수집 기간 밖의 글을 골라 한 번 시트로 보낸다(분류 포함).

  python scripts/send_posts.py NIA notice 28771 28987

지금은 NIA 공지사항·보도자료만 지원한다(글 목록 1쪽에 있어야 한다. 고정 글은 늘 1쪽에 있다).
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harvest import classify, collect, sheet  # noqa: E402
from harvest.sources import nia  # noqa: E402
from harvest.sources.base import Http, Post, pick_attachments  # noqa: E402


def main(agency: str, kind: str, ids: list[str]) -> int:
    assert agency == "NIA", "지금은 NIA만 지원한다"
    cb = dict(nia.BOARDS)[kind]
    http = Http()
    res = http.get(f"{nia.BASE}/site/nia_kor/ex/bbs/List.do", params={"cbIdx": cb, "pageIndex": 1})
    rows = {no: (title, date) for no, title, date in nia.parse_list(res.text, cb)}
    agencies = collect.load_agencies()
    client = classify.client()
    posts, results = [], {}
    for no in ids:
        title, date = rows[no]
        url = f"{nia.BASE}/site/nia_kor/ex/bbs/View.do?cbIdx={cb}&bcIdx={no}&parentSeq={no}"
        body, atts = nia.parse_detail(http.get(url).text, url)
        p = Post("NIA", kind, no, title, date, url, body=body, attachments=pick_attachments(atts))
        results[p.key] = r = classify.classify(client, p, agencies["NIA"])
        print(f"{date} {title} | 첨부 {','.join(a.ext for a in p.attachments)} | {r['recommend']}/{r['doc_type']} · {r['doc_name']}")
        posts.append(p)
    now = datetime.datetime.now(collect.KST)
    print("시트 전송:", sheet.post_rows(collect.to_rows(posts, agencies, now, results)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
