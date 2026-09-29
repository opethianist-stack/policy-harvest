"""Apps Script(구글 서버)가 받을 수 없는 첨부를 러너가 대신 받아 시트 웹 앱의 중계 폴더에 넣는다.

  python -m harvest.relay

과기정통부(www.msit.go.kr)는 해외 구글 서버의 접속을 받지 않지만 GitHub 러너에서는 받아진다(2026-09-29 확인).
relay 워크플로가 매일 00:30 KST에 돌고, 01:00 deliverApproved가 중계 폴더의 파일로 저장한다.
"""

from __future__ import annotations

import base64
import sys

from . import sheet
from .collect import APPS_SCRIPT_UA
from .sources.base import Http

MAX_BYTES = 35 * 1024 * 1024  # Apps Script RELAY_MAX_BYTES 와 같다


def check(status: int, content: bytes) -> str | None:
    """받은 응답이 파일로 쓸 만한지. 문제가 있으면 이유를 돌려준다."""
    if status != 200:
        return f"HTTP {status}"
    if len(content) < 1024:
        return f"파일이 너무 작음({len(content)}B)"
    if len(content) > MAX_BYTES:
        return f"파일이 너무 큼({len(content)}B)"
    if content.lstrip()[:1] == b"<":
        return "HTML 응답(오류 페이지일 수 있음)"
    return None


def main() -> int:
    rows = sheet.relay_list()
    print(f"중계할 첨부 {len(rows)}건")
    http = Http()
    failed = 0
    for r in rows:
        url = r["att_url"]
        try:
            res = http.get(url, timeout=120, headers={"User-Agent": APPS_SCRIPT_UA, "Referer": r.get("post_url", "")})
            problem = check(res.status_code, res.content)
            if problem:
                raise RuntimeError(problem)
            out = sheet.relay_put(url, base64.b64encode(res.content).decode("ascii"))
            print(f"  넣음 {out.get('bytes')}B {url}")
        except Exception as e:  # 한 건이 실패해도 나머지는 넣는다
            failed += 1
            print(f"  실패 {url}: {e}")
    if failed:
        print(f"실패 {failed}건. 다음 실행에서 다시 시도한다")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
