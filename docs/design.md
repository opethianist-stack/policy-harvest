# policy-harvest 설계 (초안)

## 1. 목적과 원칙

부처와 공공기관이 게시하는 정책문서(보도자료·업무계획·기본계획·경영목표·사업계획)를 주 1회 모아 LLM으로 분류하고, 담당자가 승인한 원본 파일만 Policy Fit 정책문서 폴더(`1-VLB42YhmZZIMxoR48J2qeIYgMYMdAK5`)에 넣는다.

- LLM은 추천까지만 한다. 승인되지 않은 파일은 폴더에 들어가지 않는다
- 폴더에는 기관이 게시한 원본 파일을 그대로 넣는다. 예외: Policy Fit이 읽지 못하는 odt만 올라온 경우 PDF로 변환해 넣고 상태 열에 표시한다(2026-09-28 결정)
- Policy Fit과는 드라이브 폴더로만 연결한다. Policy Fit은 매일 03:00(KST)에 폴더를 읽어 색인한다
- 별도 서버나 웹앱은 두지 않는다. 실행은 GitHub Actions, 승인 화면은 구글 시트다

## 2. 첫 버전 범위

| 포함 | 제외 |
|---|---|
| 부처 4곳: 과기정통부(API), 교육부·고용노동부·국가AI전략위(사이트) | 그 밖의 부처 |
| 시도교육청 17곳 주요업무계획(연 1회) | |
| 공공기관 5곳: NIPA, NIA, KERIS, KOSAC, KEDI | KICE |
| 보도자료, 정책자료, NIA·KERIS 공지사항 | 입찰공고·사업공고(Policy Fit으로 인계, `docs/handoff-policy-fit.md`) |
| | 정책브리핑(RSS 중단) |
| 경영공시·경영목표 페이지의 첨부 변경 감지 | 알리오 경영공시 원문 수집(구조 미조사) |
| 주 1회 수집, 글 단위 LLM 분류 | 임베딩 검색(RAG) |
| 구글 시트 승인, 승인분 드라이브 업로드 | 나라장터 발주계획(KERIS, Policy Fit으로 인계) |
| | 알리오플러스 API(기관정보 보강용, 2차) |

공고성 게시판은 정책문서 폴더의 성격과 맞지 않아 넣지 않는다. 공고는 Policy Fit이 나라장터·부처 사업공고 API로 다루는 영역이다.

NIA·KERIS는 업무계획을 별도로 공시하지 않고 공지사항에 올린다(담당자 확인). 공지사항 전체를 받고 분류에서 정책문서만 남긴다. 공지에 섞인 사업 모집은 `제외`로 분류되고, 공고로서는 Policy Fit이 따로 다룬다.

부처 문서는 Policy Fit 폴더에서 가장 많은 분류다(2026-09-24 기준 색인 파일 27개 중 부처 18, 교육청 4, 공공기관 3, 협의체 2). 부처는 보도자료에 업무계획·기본계획을 붙임 파일로 올리는 경우가 많아 보도자료 수집이 중심이다.

### 시도교육청

- 17개 시도교육청의 연간 주요업무계획. 주간 수집이 아니라 12월~2월에 위치를 한 번 확인한다
- 파일명 `19-N_교육청_<정식 명칭>_<교육청이 붙인 문서명>_2026.pdf`. 번호는 시도 순서로 고정(`sources.yaml`의 `file_no`)
- 자동으로 받는 곳 11, 담당자가 직접 받는 곳 6(robots.txt 차단 3, 해외 접속 차단 2, 위치 미확인 1). 목록과 링크는 `docs/edu-offices-2026.md`
- 서울은 기존 12번 파일과 같은 문서라 올리지 않는다

## 3. 전체 흐름

```
[월 06:00 KST] collect 워크플로
  게시판 목록 → 새 글 판별(시트의 글 키와 대조) → 상세·첨부 목록
  → LLM 분류(글 단위) → 시트에 행 추가(첨부 1개당 1행)

[담당자] 시트에서 확인
  추천 분류·문서명 확인, 필요하면 수정, 승인 칸 체크

[매일 01:00 KST] 승인 시트의 Apps Script (deliverApproved)
  승인 행 읽기 → 원본 첨부 다운로드 → 파일명 생성 → 드라이브 저장
  → 시트에 전송 결과 기록

[매일 03:00 KST] Policy Fit sync-corpus (기존)
  폴더 색인
```

01:00에 저장하면 승인한 파일이 그날 새벽 Policy Fit 색인에 들어간다. 급하면 Apps Script 편집기에서 `deliverApproved`를 바로 실행한다.

## 4. 저장소 구성

```
config/sources.yaml        기관·게시판 설정
harvest/
  sources/                 기관별 수집기
    base.py                공통 인터페이스, HTTP 세션(UA·간격·재시도)
    msit.py                과기정통부(공공데이터포털 API)
    moe.py                 교육부(사이트)
    nipa.py nia.py keris.py kosac.py kedi.py
  classify.py              LLM 분류
  sheet.py                 승인 시트로 행 보내기(Apps Script 웹 앱)
  naming.py                파일명 규칙
  collect.py               collect 진입점
tests/fixtures/            기관별 저장 HTML(수집기 파서 시험용)
.github/workflows/
  collect.yml  probe.yml  tests.yml
apps-script/Code.gs        승인 시트 스크립트(행 추가, 승인분 드라이브 저장)
docs/
```

## 5. 수집기

### 인터페이스

```python
class Source:
    def list_posts(self, board) -> list[Post]        # 목록 1페이지(최신순)
    def fetch_detail(self, post) -> Detail           # 본문 텍스트, 첨부 목록
```

- `Post`: `agency, board_kind, post_id, title, posted_at, url`
- `Detail`: `body_text`, `attachments[name, url, ext, size]`
- 글 키: `{agency}:{board_kind}:{post_id}`. 시트에 이미 있는 키는 건너뛴다

### 기관별 처리

| 기관 | 목록 | 상세 주소 | 비고 |
|---|---|---|---|
| 과기정통부 | 공공데이터포털 API(보도자료·주요정책) | 응답의 `viewUrl` | 한 페이지 최대 10건. 첨부 `fileUrl`은 로그인 없이 받아진다. hwpx+odt 쌍이면 hwpx를 보낸다(Policy Fit 색인은 odt를 읽지 않음) |
| 교육부 | 보도자료 표, `listRenew.do?boardID=294&page=N` | `goView('294','boardSeq')` → `viewRenew.do?boardID=294&boardSeq=` | 구현(`harvest/sources/moe.py`). 첨부 `fileDown.do?fileSeq=`, 이름은 `.atta-inner`에서 크기 표시를 떼어 쓴다. 올해 업무계획 페이지(`infoRenew.do?page=72762`)의 `/upload/filedown/{연도}_business_plan_*.pdf`를 연 1회 글로 올린다 |
| 고용노동부 | 보도자료·정책자료실 표, `?pageIndex=N` | `enewsView.do?news_seq=`, `policydata/view.do?bbs_seq=` | 구현(`harvest/sources/moel.py`). 첨부 `downloadFile.do`. 소속기관(공단·폴리텍 등) 보도자료가 많이 섞여 분류에서 거른다. 업무보고 메뉴는 스크립트로 그려 받지 않는다 |
| 국가AI전략위 | JSON `brdList.do?menu_cd=&currentPage=N` | JSON `brdDetail.do?menu_cd=&num=` | 구현(`harvest/sources/naisc.py`). 000012 보도자료, 000011 정책자료. 첨부 `/attach/cms/board/{subpath}/{file_save}`. 000014는 인터뷰·기고라 제외 |
| NIPA | 표(`table.tb01`), `?curPage=N` | `/home/4-4-1/{글번호}` | 구현(`harvest/sources/nipa.py`). 보도자료마다 pdf와 "보도자료(HWPX)및사진.zip"이 함께 올라와 pdf가 있으면 zip은 뺀다. 첨부 `/comm/getFile?...` |
| NIA | 목록 태그(li), `?cbIdx=&pageIndex=N` | `doBbsFView('cbIdx','bcIdx',…)` → `View.do?cbIdx=&bcIdx=&parentSeq=` (GET으로 열린다) | 구현(`harvest/sources/nia.py`). 보도자료·공지사항. 제목은 링크 title 속성. 공지사항은 옛 고정 글이 위에 붙어 페이지 마지막 행 날짜로 멈춘다 |
| KERIS | 표, `?mi=&bbsId=&currPage=N` | `nttView('nttSn')` → `selectNttInfo.do?mi=&nttSn=&bbsId=` | 구현(`harvest/sources/keris.py`). 보도자료·공지사항. 첨부 서버가 Content-Type을 `application-download`로 준다(Apps Script `blobOf_`가 처리). 보도자료의 행사 사진은 뺀다 |
| KOSAC | 표(`table.board_list`, tbody 없음), 기본 목록 → `?page=1`… | `/menus/272/boards/394/posts/{글번호}` | 구현(`harvest/sources/kosac.py`). 다운로드 버튼 href가 비어 있어 첨부 주소는 페이지 데이터의 `cdn.kosac.re.kr/files/cms/attach/…`, 이름은 `.view_file`에서 같은 순서로 짝짓는다. 구분 칸도 `class="date"`라 날짜가 있는 칸을 읽는다. 보도자료가 한 달에 1~4건 |
| KEDI | 확인 필요 | `selectAnnounceForm.do?board_sq_no=3&article_sq_no=` | 목록 요청 흐름 확인 필요 |

경영공시·경영목표 페이지(NIPA `/home/3-2`, KOSAC `/menus/331`·`/menus/208`, KEDI `managementgoal.do`·`businessplan.do`)는 게시판이 아니다. 페이지의 첨부 링크 목록을 글처럼 다루고, 새 첨부가 나타날 때만 행을 만든다. 글 키는 `{agency}:disclosure:{첨부 URL 해시}`로 한다.

### 요청 예절

- 주 1회, 게시판당 목록 1페이지만 읽는다. 첫 실행만 최근 3페이지를 읽는다
- 요청 간격 1초 이상, 기관당 동시 요청 1개
- User-Agent에 봇 이름과 레포 주소를 밝힌다
- robots.txt를 실행마다 읽고 막힌 경로는 건너뛴다(KERIS처럼 읽을 수 없으면 기존 동작 유지)

## 6. 분류

### 입력

기관, 게시판 종류, 제목, 게시일, 본문 앞부분(최대 3,000자), 첨부 파일명 목록.

첨부 내용은 첫 버전에서 읽지 않는다. 제목·본문·첨부명으로 판단이 어려운 경우가 많으면 2차에서 첨부 첫 쪽 텍스트를 추가한다.

### 출력 (JSON 스키마로 고정)

| 필드 | 값 |
|---|---|
| `recommend` | `포함` / `제외` |
| `doc_type` | 업무계획, 기본계획·종합계획, 경영목표, 사업계획, 보도자료, 기타 |
| `topics` | 주제 태그 최대 3개(예: AI교육, 디지털교과서, 교원연수) |
| `doc_name` | 파일명에 쓸 문서명. 공백·밑줄 없이 |
| `year` | 문서 연도 |
| `primary_attachment` | 원본으로 보낼 첨부 번호(본문 첨부·붙임이 여럿일 때) |
| `reason` | 추천 이유 한 문장 |

- `포함` 기준은 "기관의 정책 방향·계획을 담은 문서인가"다. 보도자료 중 행사 개최 안내, 수상·협약 소식, 인사·채용 등은 `제외`. 계획 발표·정책 추진 보도와 그 붙임 계획서는 `포함`
- 모델 기본값: `claude-opus-5`(effort `low`, 구조화 출력). 환경변수 `CLASSIFY_MODEL`로 바꿀 수 있다(예: `claude-haiku-4-5`). 주 수십 건 규모라 비용은 주당 1달러 안팎. 시트에 이미 있는 글은 다시 분류하지 않는다
- 키: Actions Secrets `ANTHROPIC_API_KEY`. 작업 환경에서는 `POLICYFIT_ANTHROPIC_KEY`를 쓴다(작업 환경이 `ANTHROPIC_API_KEY`를 넘기지 않음)
- 응답이 스키마와 다르면 한 번 다시 요청하고, 그래도 실패하면 `recommend=검토 필요`로 시트에 넣는다

## 7. 승인 시트

시트 1개, 탭 `inbox`. 첨부 1개가 1행이다. 같은 글의 첨부는 `글 키`가 같다.

| 열 | 작성 | 내용 |
|---|---|---|
| 수집일 | 수집기 | |
| 글 키 | 수집기 | 중복 판별 기준 |
| 기관 | 수집기 | NIPA 등 파일명 약칭 |
| 게시판 | 수집기 | |
| 제목 | 수집기 | 원문 글 링크를 건다 |
| 게시일 | 수집기 | |
| 첨부 | 수집기 | 파일명, 다운로드 링크 |
| 추천 | LLM | 포함 / 제외 / 검토 필요 |
| 문서 유형 | LLM | |
| 주제 | LLM | |
| 추천 이유 | LLM | |
| 문서명 | LLM → 담당자 | 수정 가능 |
| 구분 | LLM → 담당자 | 별첨·보도 등. 비워도 됨 |
| 연도 | LLM → 담당자 | 수정 가능 |
| 승인 | 담당자 | 체크박스 |
| 상태 | Apps Script | 대기 / 전송 완료 / 실패(사유) |
| 파일명 | Apps Script | 실제로 올린 파일명 |
| 드라이브 링크 | Apps Script | |

- `추천=포함`이고 대표 첨부인 행을 위로 정렬하고, `제외`는 회색으로 표시한다
- 승인은 담당자 체크로만 바뀐다. 수집기·LLM은 승인 칸을 쓰지 않는다
- 시트가 원장이다. 별도 DB는 두지 않는다

## 8. 드라이브 업로드

### 파일명

`번호_분류_기관_문서명[_구분]_연도.확장자` (Policy Fit `scripts/build_index.py` 규칙)

- 분류는 `sources.yaml`의 `category`(부처 / 공공기관)
- 기관은 `file_org`. Policy Fit `data/org-rules.json` 별칭과 맞춘다. 과기정통부·교육부는 기존 폴더 표기 그대로, NIPA·NIA·KERIS·KEDI는 약칭, 한국과학창의재단은 `KOSAC`(별칭 등록됨)
- Policy Fit 색인이 읽는 형식은 pdf·hwpx·hwp다. 첨부 형식별 처리:
  - pdf·hwpx·hwp: 그대로 저장
  - odt: 구글 문서로 변환해 PDF로 저장. 한글 프로그램에서 내보낸 odt는 변환하면 모든 글자에 취소선이 붙으므로 취소선을 지운 뒤 내보낸다
  - zip: 풀어서 안의 pdf·hwpx·hwp·odt·xlsx를 저장(같은 문서가 여러 형식이면 하나만). 하위 번호(`12-1`, `12-2`)와 구분 칸에 원래 파일명을 붙인다
  - xlsx·xls: 통계·데이터 자료라 원본 그대로 저장한다. Policy Fit이 xlsx를 읽기 전까지는 색인되지 않는다
  - 이미지(jpg·png 등): 글자가 없어 색인되지 않으므로 수집 단계에서 뺀다
  - 그 밖의 형식: 시트에는 올라가지만 승인해도 `실패: 저장하지 않는 형식`
- 번호: 폴더에 있는 파일명의 맨 앞 번호 중 가장 큰 값 + 1. 같은 글에서 여러 파일을 올리면 `12-1`, `12-2`처럼 하위 번호를 붙인다
- 문서명에서 `_`와 파일명 금지 문자는 지운다
- 같은 이름이 이미 있으면 올리지 않고 `실패(중복)`로 기록한다

### 업로드 주체: 승인 시트의 Apps Script (B안, 2026-09-27 결정)

- 폴더는 부서 공통 gmail 계정의 내 드라이브에 있다. 서비스 계정은 저장 용량이 없어 새 파일을 만들 수 없고, 부서 계정에 OAuth 앱을 등록·게시하는 A안은 관리 부담이 커서 쓰지 않는다
- 승인 시트(부서 계정 소유)에 붙인 Apps Script가 부서 계정 권한으로 원본을 받아 폴더에 저장한다. 올린 파일의 소유자는 부서 계정
- 수집기는 시트에 행만 보낸다(Apps Script 웹 앱 `doPost`, 공유 TOKEN으로 확인)
- 번호: 폴더 파일명의 맨 앞 번호 최댓값 + 1. 같은 글에서 두 개 이상 승인하면 `20-1`, `20-2`
- Apps Script `UrlFetchApp` 응답 한도는 50MB다. 그보다 큰 파일(예: 광주 주요업무계획 98MB)은 실패로 표시되고 담당자가 직접 넣는다
- 코드: `apps-script/Code.gs`(원본은 레포), `harvest/sheet.py`. 설정 절차: `docs/setup-apps-script.md`

## 9. 비밀값

| 이름 | 용도 | 위치 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 분류 | Actions Secrets |
| `SHEET_WEBHOOK_URL`·`SHEET_WEBHOOK_TOKEN` | 수집기 → 승인 시트 행 전송 | Actions Secrets |
| `ALIO_*_KEY` | 2차 알리오플러스 연동 | Actions Secrets |

## 10. 구현 순서

1. 수집기: 과기정통부(API) → NIPA·KOSAC(일반 링크) → NIA·KERIS(JS 상세) → 교육부·KEDI(구조 조사 후). 기관별 저장 HTML로 파서 시험
2. 시트 연동: 시트 생성·서비스 계정 공유, 행 추가·중복 판별
3. 분류: 프롬프트·스키마, 지난 글 수십 건으로 추천 결과 점검
4. collect 워크플로 주간 실행
5. 승인 시트·Apps Script 설정(`docs/setup-apps-script.md`) 후 승인분 저장 시험
6. 경영공시 페이지 첨부 변경 감지

## 11. 결정이 필요한 것

| 항목 | 제안 |
|---|---|
| 승인 시트 소유 계정 | 부서 공통 gmail 계정 |
| 첫 실행 수집 범위 | 게시판당 최근 3페이지 |
| 수집 요일·시각 | 월 06:00 KST |
| NIA·KERIS 업무계획·경영목표 출처 | 알리오 경영공시 조사 후 결정 |
| 알리오 경영공시 원문 | 2차에서 웹 화면 조사 후 결정 |
