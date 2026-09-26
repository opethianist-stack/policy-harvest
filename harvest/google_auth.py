"""부서 구글 계정 OAuth 인증.

정책문서 폴더는 부서 공통 gmail 계정의 내 드라이브에 있다. 서비스 계정은 저장 용량이 없어
그 폴더에 파일을 만들 수 없으므로, 부서 계정의 리프레시 토큰으로 드라이브·시트를 쓴다.

환경변수(GitHub Secrets):
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  GOOGLE_OAUTH_REFRESH_TOKEN
"""

from __future__ import annotations

import os

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
ENV_KEYS = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def missing_env() -> list[str]:
    return [k for k in ENV_KEYS if not os.environ.get(k, "").strip()]


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    missing = missing_env()
    if missing:
        raise RuntimeError(f"OAuth 환경변수가 없습니다: {', '.join(missing)}")
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"].strip(),
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def drive_service(creds=None):
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds or credentials(), cache_discovery=False)


def sheets_service(creds=None):
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=creds or credentials(), cache_discovery=False)
