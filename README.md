# policy-harvest

교육·과학기술 분야 부처·공공기관·시도교육청의 정책문서를 수집하고 LLM으로 분류한 뒤, 담당자가 승인한 원본만 Policy Fit 정책문서 드라이브 폴더로 보낸다.

## 대상

| 기관 | 이름 | 분류·주무부처 |
|---|---|---|
| 과기정통부 | 과학기술정보통신부 | 부처 |
| 교육부 | 교육부 | 부처 |
| 고용노동부 | 고용노동부 | 부처 |
| 국가AI전략위 | 국가인공지능전략위원회 | 부처 |
| NIPA | 정보통신산업진흥원 | 과학기술정보통신부 |
| NIA | 한국지능정보사회진흥원 | 과학기술정보통신부 |
| KERIS | 한국교육학술정보원 | 교육부 |
| KOSAC | 한국과학창의재단 (구 KOFAC) | 과학기술정보통신부 |
| KEDI | 한국교육개발원 | 국무조정실(경제·인문사회연구회) |
| 시도교육청 17곳 | 주요업무계획(연 1회) | 교육청 |

문서 종류: 보도자료, 업무계획, 기본계획, 경영목표, 사업계획 (정책문서만. 입찰·사업공고는 Policy Fit으로 인계: `docs/handoff-policy-fit.md`)

## 원칙

- LLM 판정은 추천까지만 한다. 담당자 승인 없이 드라이브 폴더에 넣지 않는다.
- 폴더에는 가공본이 아니라 기관이 게시한 원본 파일을 넣는다.
- Policy Fit과는 드라이브 폴더로만 연결한다. Policy Fit은 폴더를 매일 새벽 색인한다.
- 파일명 규칙: `번호_분류_기관_문서명[_구분]_연도.확장자` (Policy Fit `scripts/build_index.py`와 같다. 분류는 `부처`·`공공기관`·`교육청`)
- 승인은 구글 시트에서 한다. 수집 결과를 시트에 행으로 쌓고, 담당자가 승인한 행만 시트에 붙인 Apps Script가 부서 계정 권한으로 드라이브 폴더에 저장한다. 별도 서버는 두지 않는다.

## 구성

```
config/sources.yaml          수집 대상 기관·게시판 설정
probe/                       1단계 사전 조사 스크립트
harvest/                     수집기 모듈(파일명 규칙, 승인 시트 전송)
apps-script/Code.gs          승인 시트 스크립트(행 추가, 승인분 드라이브 저장)
.github/workflows/probe.yml  사전 조사 워크플로 (Actions 러너에서 접속 확인)
docs/research.md             1단계 사전 조사 결과
docs/design.md               설계 (초안)
docs/handoff-policy-fit.md   Policy Fit으로 넘긴 공고 게시판 정보
docs/edu-offices-2026.md     시도교육청 2026 주요업무계획 위치·파일명
docs/setup-apps-script.md    승인 시트·드라이브 업로드 설정
```

## 진행 단계

1. 사전 조사
   - 기관 사이트 접속성, 게시판 HTML 구조(정적/JS), robots.txt 확인: `probe-sites` 워크플로
   - 알리오 경영공시 원문 파일과 알리오플러스 API 제공 범위 확인
   - 정책브리핑 보도자료가 산하기관 자료를 담는지 확인 → RSS 서비스 중단, 대체 API 없음. 수집 경로에서 제외
2. 설계 문서: 구조, 데이터 흐름, 첫 버전 범위
   - 첫 버전: 6개 기관 × 보도자료·경영공시, 주간 수집, 문서별 LLM 분류, 승인 목록 화면, 드라이브로 보내기
   - 임베딩 검색(RAG)은 첫 버전에서 제외

## 사전 조사 실행

```
pip install -r probe/requirements.txt
python probe/probe_sites.py   # 결과: out/probe.md, out/probe.json
```

Actions에서는 `probe/`, `config/sources.yaml`이 바뀌어 push되면 자동 실행되고, Actions 탭에서 수동 실행도 된다. 결과는 실행 요약과 `probe-result` 아티팩트로 남는다.
