# 드라이브·시트 업로드 인증 설정 (A안: 부서 계정 OAuth)

정책문서 폴더를 가진 부서 공통 gmail 계정으로 한 번 로그인해 리프레시 토큰을 받고, GitHub Secrets에 넣는다. 이후 GitHub Actions가 이 토큰으로 폴더에 파일을 올리고 승인 시트를 읽고 쓴다. 올린 파일의 소유자는 부서 계정이 된다.

## 1. 구글 클라우드 설정 (부서 계정으로 로그인)

1. [Google Cloud 콘솔](https://console.cloud.google.com/)에서 프로젝트를 고른다. Policy Fit의 `policy-fit` 프로젝트를 써도 되고 새로 만들어도 된다
2. **API 및 서비스 → 라이브러리**에서 `Google Drive API`, `Google Sheets API`를 사용 설정
3. **OAuth 동의 화면**
   - 사용자 유형: 외부
   - 앱 이름: policy-harvest, 지원 이메일: 부서 계정
   - 범위는 비워 둬도 된다(토큰 발급 때 요청)
   - **게시 상태를 "프로덕션 단계"로 바꾼다.** "테스트" 상태로 두면 리프레시 토큰이 7일 뒤 만료된다. 검수는 받지 않아도 되며, 로그인할 때 "확인되지 않은 앱" 경고가 나오면 고급 → 이동을 누른다
4. **사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 만든 뒤 JSON을 내려받는다(`client_secret_….json`). 레포에 올리지 않는다

## 2. 리프레시 토큰 발급

### 방법 1: PC에서 스크립트 실행

```
pip install google-auth-oauthlib
python scripts/get_refresh_token.py client_secret_….json
```

브라우저가 열리면 **부서 계정**으로 로그인해 드라이브·스프레드시트 권한을 허용한다. 터미널에 값 3개가 출력된다.

### 방법 2: 브라우저만으로 (OAuth 2.0 Playground)

1. 1-4에서 만든 클라이언트를 **웹 애플리케이션** 유형으로 하나 더 만들고, 승인된 리디렉션 URI에 `https://developers.google.com/oauthplayground`를 넣는다
2. [OAuth 2.0 Playground](https://developers.google.com/oauthplayground) 오른쪽 위 톱니바퀴 → "Use your own OAuth credentials" 체크 → 클라이언트 ID·보안 비밀 입력
3. 왼쪽 "Input your own scopes"에 아래 두 줄을 공백으로 이어 넣고 Authorize APIs → 부서 계정으로 로그인
   ```
   https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets
   ```
4. "Exchange authorization code for tokens" → Refresh token 값을 복사

## 3. GitHub Secrets 등록

레포 **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | 클라이언트 ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | 클라이언트 보안 비밀 |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | 리프레시 토큰 |

값은 채팅이나 레포 파일에 붙이지 않는다.

## 4. 확인

Actions → **drive-check** → Run workflow(또는 담당 세션에 확인 요청). 성공하면 다음이 나온다.

- 로그인 계정(부서 계정이어야 한다)
- 폴더 파일 추가 권한 `True`
- 규칙과 다른 파일명 목록, 다음 문서 번호
- 시험 파일 업로드 성공 → 삭제 완료

## 토큰이 무효가 되는 경우

- 부서 계정 비밀번호 변경(드라이브 범위를 가진 토큰은 비밀번호 변경 시 폐기됨)
- 계정 보안 설정에서 앱 접근 권한 삭제
- 6개월 동안 한 번도 쓰지 않음
- OAuth 동의 화면이 "테스트" 상태(7일)

이때는 2~3단계를 다시 한다.
