"""부서 계정 리프레시 토큰 발급(담당자 PC에서 한 번 실행).

  pip install google-auth-oauthlib
  python scripts/get_refresh_token.py client_secret.json

브라우저가 열리면 부서 공통 gmail 계정으로 로그인해 권한을 허용한다.
출력된 값 3개를 GitHub Secrets에 등록한다. client_secret.json 과 출력값은 레포에 올리지 않는다.
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: python scripts/get_refresh_token.py <client_secret.json>")
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    info = json.load(open(sys.argv[1], encoding="utf-8"))
    client = info.get("installed") or info.get("web") or {}
    print("GOOGLE_OAUTH_CLIENT_ID =", client.get("client_id"))
    print("GOOGLE_OAUTH_CLIENT_SECRET =", client.get("client_secret"))
    print("GOOGLE_OAUTH_REFRESH_TOKEN =", creds.refresh_token)


if __name__ == "__main__":
    main()
