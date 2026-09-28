"""승인 시트 연결 확인: 시험 행 1개를 두 번 보낸다(두 번째는 중복으로 건너뛰어야 한다)."""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harvest import sheet  # noqa: E402


def main() -> int:
    missing = sheet.missing_env()
    if missing:
        print(f"시트 환경변수가 없어 확인을 건너뜁니다: {', '.join(missing)}")
        return 0
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    row = {
        "collected_at": now.strftime("%Y-%m-%d %H:%M"),
        "post_key": f"TEST:check:{now:%Y%m%d%H%M%S}",
        "category": "공공기관",
        "org": "TEST",
        "board": "연결시험",
        "title": "[시험] policy-harvest 연결 확인 (삭제해도 됨)",
        "post_url": "https://github.com/opethianist-stack/policy-harvest",
        "posted_at": now.strftime("%Y-%m-%d"),
        "att_name": "dummy.pdf",
        "att_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "recommend": "제외",
        "doc_type": "기타",
        "topics": ["시험"],
        "reason": "연결 확인용 행",
        "doc_name": "연결시험",
        "year": "2026",
    }
    first = sheet.post_rows([row])
    second = sheet.post_rows([row])
    print(f"1차 전송: {first}")
    print(f"2차 전송(같은 행): {second}")
    ok = first == {"added": 1, "skipped": 0} and second == {"added": 0, "skipped": 1}
    print("결과:", "정상" if ok else "예상과 다름")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
