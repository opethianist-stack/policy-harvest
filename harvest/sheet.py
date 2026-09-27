"""승인 시트로 행 보내기.

시트에 붙은 Apps Script 웹 앱(apps-script/Code.gs 의 doPost)으로 POST 한다.
환경변수(GitHub Secrets):
  SHEET_WEBHOOK_URL    웹 앱 배포 URL(…/exec)
  SHEET_WEBHOOK_TOKEN  Apps Script 스크립트 속성 TOKEN 과 같은 값
"""

from __future__ import annotations

import os
import time

import requests

FIELDS = (
    "collected_at", "post_key", "category", "org", "board", "title", "post_url", "posted_at",
    "att_name", "att_url", "recommend", "doc_type", "topics", "reason", "doc_name", "kind", "year",
)
BATCH = 200
RETRIES = 3  # 시트가 중복을 걸러주므로 다시 보내도 안전하다


def missing_env() -> list[str]:
    return [k for k in ("SHEET_WEBHOOK_URL", "SHEET_WEBHOOK_TOKEN") if not os.environ.get(k, "").strip()]


def post_rows(rows: list[dict], session: requests.Session | None = None) -> dict:
    """행을 보내고 {"added": n, "skipped": m}를 돌려준다. 중복 판별은 시트 쪽에서 한다."""
    missing = missing_env()
    if missing:
        raise RuntimeError(f"시트 환경변수가 없습니다: {', '.join(missing)}")
    unknown = {k for r in rows for k in r} - set(FIELDS)
    if unknown:
        raise ValueError(f"시트에 없는 필드: {sorted(unknown)}")
    s = session or requests.Session()
    total = {"added": 0, "skipped": 0}
    for i in range(0, len(rows), BATCH):
        data = _post_batch(s, rows[i:i + BATCH])
        if not data.get("ok"):
            raise RuntimeError(f"시트 응답 오류: {data.get('error')}")
        total["added"] += data.get("added", 0)
        total["skipped"] += data.get("skipped", 0)
    return total


def _post_batch(s, batch: list[dict], sleep=time.sleep) -> dict:
    """한 묶음 전송. 웹 앱 결과 주소가 404·5xx를 주는 경우가 있어 몇 번 다시 보낸다."""
    last_err = None
    for attempt in range(RETRIES):
        try:
            # Apps Script 웹 앱은 302로 결과 주소를 돌려준다. requests는 따라가며 GET으로 바꾼다
            res = s.post(
                os.environ["SHEET_WEBHOOK_URL"].strip(),
                json={"token": os.environ["SHEET_WEBHOOK_TOKEN"].strip(), "rows": batch},
                timeout=90,
            )
            res.raise_for_status()
            return res.json()
        except (requests.RequestException, ValueError) as e:
            last_err = e
            if attempt + 1 < RETRIES:
                sleep(5 * (attempt + 1))
    raise RuntimeError(f"시트 전송 실패({RETRIES}회): {last_err}")
