# 1단계 사전 조사 결과

조사일: 2026-09-26
실행 환경: GitHub Actions `ubuntu-latest` 러너(미국 애리조나, Microsoft AS8075)
조사 도구: `probe/probe_sites.py`, 워크플로 `probe-sites`(1~10차 실행)

## 1. 요약

| 항목 | 결론 |
|---|---|
| 기관 사이트 접속 | 5개 기관(NIPA·NIA·KERIS·KOSAC·KEDI) 모두 해외 러너에서 접속된다. IP 차단 없음 |
| 게시판 구조 | 모두 서버가 HTML 목록을 그려서 내려준다. 브라우저 자동화 없이 수집할 수 있다 |
| 상세 링크 | NIA·KERIS는 상세 페이지를 JS 함수로 연다. 함수 인자에서 글 번호를 읽어 주소를 만들어야 한다 |
| robots.txt | 조사 대상 게시판 경로를 막는 기관은 없다. NIA는 Googlebot에만 `/site/nia_kor/ex/bbs/`를 막았다 |
| 정책브리핑 | RSS 서비스 중단. data.go.kr에도 대체 API가 없다. 수집 경로에서 제외 |
| 알리오플러스 API | 기관정보·사업정보·행사정보·시설정보 4종. 경영공시 원문 파일(사업계획·경영목표)은 제공하지 않는다 |
| KICE | 수집 대상에서 제외(해당 기관 사업 비중이 낮음) |

## 2. 기관별 결과

### NIPA 정보통신산업진흥원 (`www.nipa.kr`)

- 홈 `/`는 `/home/index`로 이동한다. 메뉴 링크가 HTML에 모두 있다(링크 384개)
- robots.txt: Googlebot의 `/sea`, `/tota`만 막는다

| 종류 | 주소 | 목록 형태 |
|---|---|---|
| 공지사항 | `/home/2-1` | 표, 행 13 |
| 사업공고 | `/home/2-2` | 표, 행 10 |
| 입찰공고 | `/home/2-3` | 표, 행 10 |
| 보도자료 | `/home/4-4-1` | 표, 행 10 |
| 경영공시 | `/home/3-2` | 공시 항목 표(행 74). 게시판이 아니라 항목 목록 |

상세 페이지는 `/home/2-1/16839`처럼 일반 링크다.

### NIA 한국지능정보사회진흥원 (`www.nia.or.kr`)

- 홈 HTML에는 메뉴 링크가 없다(링크 0개). 메뉴를 JS로 그린다. 게시판 주소는 담당자가 확인했다
- robots.txt: 전체 허용. Googlebot에만 `/site/nia_kor/ex/bbs/`(게시판 전체)와 검색을 막았다

| 종류 | 주소 | 목록 형태 |
|---|---|---|
| 입찰공고 | `/site/nia_kor/ex/bbs/List.do?cbIdx=78336` | 목록 태그, 날짜 12개 |
| 공지사항 | `/site/nia_kor/ex/bbs/List.do?cbIdx=99835` | 같음 |
| 보도자료 | `/site/nia_kor/ex/bbs/List.do?cbIdx=90549` | 같음 |

상세 페이지는 `javascript:` 함수 호출로 연다(목록당 24개).

### KERIS 한국교육학술정보원 (`www.keris.or.kr`)

- 홈 `/`는 `/index.do`로 이동한 뒤 "존재하지 않는 홈페이지입니다."만 돌려준다. 게시판 주소는 담당자가 확인했다
- robots.txt 요청은 매번 연결이 끊긴다(응답 없음)

| 종류 | 주소 | 목록 형태 |
|---|---|---|
| 입찰공고 | `/main/tender/view/selectTenderList.do?mi=1076` | 표, 행 10 |
| 공지사항 | `/main/na/ntt/selectNttList.do?mi=1051&bbsId=1088` | 표, 행 11 |
| 보도자료 | `/main/na/ntt/selectNttList.do?mi=1088&bbsId=1090` | 표, 행 10 |

- 상세 페이지는 JS 함수 호출로 연다(목록당 27~38개)
- 공지사항에 사업(선도교사 양성연수 등)이 함께 올라온다
- 발주계획은 나라장터 발주계획 화면(기관코드 `B550629`)이라 사이트 대신 나라장터 API로 받는다

### KOSAC 한국과학창의재단 (`www.kosac.re.kr`, 구 KOFAC)

- 2025년 명칭 변경. 옛 도메인 `kofac.re.kr`은 DNS 조회가 안 된다
- Next.js 사이트지만 목록은 서버에서 완성된 HTML로 내려온다
- robots.txt: `/api/`, `/login`, `/_next/` 등만 막는다

| 종류 | 주소 | 목록 형태 |
|---|---|---|
| 사업공고 | `/menus/274/bns` | 표, 행 10 |
| 입찰공고 | `/menus/275/boards/403/posts` | 표, 행 10 |
| 보도자료 | `/menus/272/boards/394/posts` | 표, 행 10 |
| 공지사항 | `/menus/270/boards/386/posts` | 표, 행 13 |
| 경영공시 | `/menus/331/contents/331` | 콘텐츠 페이지 |

비전·경영목표는 `/menus/208/contents/208`에 있다.

### KEDI 한국교육개발원 (`www.kedi.re.kr`)

- 홈 `/`는 모바일 화면 `/khome/mobile2/webhome/Home.do`로 이동한다
- robots.txt: 4차 실행에서는 검색 경로만 막았고, 5차 실행에서는 오류 페이지가 돌아왔다

| 종류 | 주소 |
|---|---|
| 보도자료 | `/khome/mobile2/announce/listBroadAnnounceForm.do` |
| 공지사항 | `/khome/mobile2/announce/listNoticeAnnounceForm.do` |
| 입찰공고 | `/khome/mobile2/announce/listBidAnnounceForm.do` |
| 기관경영목표 | `/khome/mobile2/intro/managementgoal.do` |
| 사업계획 | `/khome/mobile2/intro/businessplan.do` |

- 다섯 페이지 모두 표 행 38·날짜 2로 같게 나왔다. 게시글 목록이 아니라 공통 레이아웃이 잡혔을 수 있다. 목록을 별도 요청으로 불러오는지 수집기 구현 때 확인해야 한다
- 홈 화면에는 날짜가 붙은 보도자료·공지·입찰 글과 상세 링크(`selectAnnounceForm.do?board_sq_no=…&article_sq_no=…`)가 있다. 게시판 번호는 공지 1, 입찰 2, 보도자료 3이다

## 2-1. 부처 (10차 실행, 2026-09-26)

| 부처 | 홈 | robots.txt | 메뉴 |
|---|---|---|---|
| 과기정통부 `www.msit.go.kr` | 200 | 검색 페이지만 막음 | JS 함수 `fn_menulast_go('user', mPid, mId, 경로)`로 연다 |
| 교육부 `www.moe.go.kr` | 200 | `/search`만 막음 | 일반 링크 |
| 고용노동부 `www.moel.go.kr` | 200. 홈은 JS로 `index.do`로 이동 | 개인정보·일부 게시판만 막음 | 게시판 주소는 웹 검색으로 확인 |
| 국가AI전략위 `www.aikorea.go.kr` | 200. 홈 응답이 메뉴 JSON | Naver(Yeti) 허용만 적혀 있고 막는 경로 없음 | `brdList.do?menu_cd=` |

| 부처 | 종류 | 주소 | 결과 |
|---|---|---|---|
| 과기정통부 | 보도자료 | `/bbs/list.do?sCode=user&mPid=208&mId=307` | 200이지만 목록 표·날짜가 잡히지 않음. 보도자료는 API로 받는다 |
| 과기정통부 | 업무계획 | `/contents/cont.do?sCode=user&mPid=80&mId=336` | 200, 내용 미확인 |
| 과기정통부 | 소관기관 업무계획 | `/bbs/list.do?sCode=user&mPid=75&mId=337` | 200이지만 목록이 잡히지 않음. 목록을 별도 요청으로 불러오는지 확인 필요 |
| 교육부 | 보도자료 | `/boardCnts/listRenew.do?boardID=294&m=020402&s=moe` | 서버 렌더링 표, 행 10 |
| 교육부 | 올해 업무계획 | `/sub/infoRenew.do?page=72762&m=031101&s=moe` | 콘텐츠 페이지, 첨부 링크 4 |
| 교육부 | 2025년 이전 주요업무계획 | `/boardCnts/listRenew.do?boardID=72713&renew=72713&m=031102&s=moe` | 서버 렌더링 표, 행 21 |
| 고용노동부 | 보도자료 | `/news/enews/report/enewsList.do` | 서버 렌더링 표, 행 10, 목록에 첨부 링크 10 |
| 고용노동부 | 정책자료실 | `/policy/policydata/list.do` | 서버 렌더링 표, 행 10. 2026년 주요업무 추진계획이 여기 있다(`view.do?bbs_seq=20251200714`) |
| 고용노동부 | 업무보고 | `/policy/busireport/main.do` | 200, 날짜 5 |
| 국가AI전략위 | `menu_cd=000011` | `/web/board/brdList.do?menu_cd=000011` | 서버 렌더링, 날짜 32. 인공지능 행동계획 원문(`num=523`)이 이 게시판에 있다 |
| 국가AI전략위 | 정책 보고서 | `/web/board/brdList.do?menu_cd=000014` | 서버 렌더링, 날짜 23 |
| 국가AI전략위 | 보도자료 | `/web/board/brdList.do?menu_cd=000018` | 200이지만 목록 없음. 검색 결과상 보도자료는 `content.do?menu_cd=000018` 형태일 수 있음 |

과기정통부 API(공공데이터포털): 보도자료·주요정책·사업공고·보도설명 4종, 한 페이지 최대 10건, 첨부 `fileUrl`은 로그인 없이 받아진다(Policy Fit `CLAUDE.md` ⑦-3). 첨부는 대부분 hwpx+odt 쌍이다.

## 3. 집계 경로

### 정책브리핑 (`www.korea.kr`)

- RSS 안내 페이지(`/etc/rss.do`)에 "정책브리핑 RSS 서비스 제공 중단 안내" 공지가 있다
- `/rss/pressrelease.xml`, `/rss/policy.xml` 모두 404
- data.go.kr에도 정책브리핑 보도자료 API가 없다(담당자 확인)

### 알리오

- `www.alio.go.kr` 홈·robots.txt 접속 정상
- 알리오플러스 Open API 4종(출처: Policy Fit `CLAUDE.md` 5장)

| API | 엔드포인트 | 키 | 내용 |
|---|---|---|---|
| 기관정보 | `/api/apba` | `ALIO_APBA_KEY` | 기관 연락처·주요사업 목록(`bsnMstList`). 기관유형 `08`이 연구교육 |
| 사업정보 | `/api/business` | `ALIO_BIZ_KEY` | 기관별 사업명·소개·지원대상·기간. 공고 게시판이 아니다 |
| 행사정보 | `/api/event` | `ALIO_EVENT_KEY` | 행사 |
| 시설정보 | `/api/facility` | `ALIO_FACILITY_KEY` | 개방 시설 |

- 호스트 `http://openapi.alioplus.go.kr`(HTTPS 미지원), POST 폼 전송, 인증키는 폼 필드 `X-API-AUTH-KEY`, `pageSize` 필수
- 경영공시 원문 파일(사업계획·경영목표 PDF 등)을 주는 API는 없다. 알리오 웹 화면에서 받을 수 있는지는 확인하지 못했다

## 4. 확인하지 못한 것

| 항목 | 이유 | 다음 조치 |
|---|---|---|
| 알리오플러스 API 실제 호출 | 작업 환경 네트워크 정책이 `openapi.alioplus.go.kr`을 막음 | 허용 도메인 추가 또는 Actions Secrets 등록 후 호출 |
| 알리오 경영공시 원문 다운로드 | 웹 화면 구조 미조사 | 기관별 공시 항목 화면과 첨부 다운로드 방식 조사 |
| KEDI 목록 구조 | 목록 페이지에서 글 목록이 확인되지 않음 | 수집기 구현 때 요청 흐름 확인 |
| NIA·KERIS 상세 페이지 | JS 함수 인자 형식 미확인 | 저장된 목록 HTML에서 함수 이름·인자 확인 |
| 첨부파일 다운로드 | 상세 페이지까지 들어가지 않음 | 기관별 첨부 링크 형식과 파일 형식(hwp·hwpx·pdf) 확인 |
