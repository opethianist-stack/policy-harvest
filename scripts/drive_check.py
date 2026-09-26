"""부서 계정 OAuth로 정책문서 폴더에 쓸 수 있는지 확인한다.

1. 토큰으로 로그인한 계정 확인
2. 폴더 파일명이 규칙에 맞는지 점검, 다음 문서 번호 계산
3. 시험 파일을 올렸다가 바로 지운다(--no-write 이면 건너뜀)

OAuth 환경변수가 없으면 안내만 하고 성공으로 끝난다.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harvest import drive, google_auth, naming  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true", help="시험 업로드를 하지 않는다")
    args = ap.parse_args()

    missing = google_auth.missing_env()
    if missing:
        print(f"OAuth 환경변수가 없어 확인을 건너뜁니다: {', '.join(missing)}")
        print("설정 방법: docs/setup-oauth.md")
        return 0

    creds = google_auth.credentials()
    svc = google_auth.drive_service(creds)
    about = svc.about().get(fields="user(emailAddress),storageQuota").execute()
    print(f"로그인 계정: {about['user']['emailAddress']}")
    q = about.get("storageQuota", {})
    if q.get("limit"):
        print(f"저장 용량: {int(q.get('usage', 0)) / 1e9:.2f} / {int(q['limit']) / 1e9:.2f} GB")

    folder = svc.files().get(
        fileId=drive.FOLDER_ID, fields="name,capabilities(canAddChildren)", supportsAllDrives=True
    ).execute()
    print(f"폴더: {folder['name']}  파일 추가 권한: {folder['capabilities']['canAddChildren']}")

    files = drive.list_names(svc)
    names = sorted(f["name"] for f in files)
    print(f"파일 {len(names)}개, 다음 문서 번호: {naming.next_group_number(names)}")
    bad = [(n, naming.check_name(n)) for n in names]
    bad = [(n, p) for n, p in bad if p]
    if bad:
        print("규칙과 다른 파일명:")
        for n, p in bad:
            print(f"  - {n}: {', '.join(p)}")

    if args.no_write:
        return 0

    name = f"_policy-harvest-연결시험_{int(time.time())}.txt"  # 색인 대상 형식이 아니라 Policy Fit이 읽지 않는다
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("policy-harvest 업로드 시험 파일. 곧바로 삭제된다.\n")
        path = fh.name
    created = drive.upload(svc, path, name)
    owner = ", ".join(o["emailAddress"] for o in created.get("owners", []))
    print(f"시험 업로드 성공: {created['name']} (소유자 {owner})")
    drive.delete(svc, created["id"])
    print("시험 파일 삭제 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
