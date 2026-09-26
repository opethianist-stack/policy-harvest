# Policy Fit 인계: 산하기관 입찰·사업공고·공지 게시판

policy-harvest는 정책문서(보도자료·업무계획·기본계획·경영목표·사업계획)만 수집한다. 아래 공고성 게시판은 Policy Fit에서 공고 소스로 검토한다.

NIA·KERIS 공지사항은 업무계획이 올라오는 곳이라 policy-harvest도 수집한다. 다만 policy-harvest는 공지 중 정책문서만 남기고 사업 모집 공지는 버리므로, 공고로서의 수집은 Policy Fit에서 따로 해야 한다.

## 게시판 목록

| 기관 | 종류 | 주소 |
|---|---|---|
| NIPA | 공지사항 | https://www.nipa.kr/home/2-1 |
| NIPA | 사업공고 | https://www.nipa.kr/home/2-2 |
| NIPA | 입찰공고 | https://www.nipa.kr/home/2-3 |
| NIA | 입찰공고 | https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=78336 |
| NIA | 공지사항 | https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835 |
| KERIS | 입찰공고 | https://www.keris.or.kr/main/tender/view/selectTenderList.do?mi=1076 |
| KERIS | 공지사항 | https://www.keris.or.kr/main/na/ntt/selectNttList.do?mi=1051&bbsId=1088 |
| KERIS | 발주계획 | 나라장터 발주계획 화면(수요기관코드 `B550629`) |
| KOSAC | 사업공고 | https://www.kosac.re.kr/menus/274/bns |
| KOSAC | 입찰공고 | https://www.kosac.re.kr/menus/275/boards/403/posts |
| KOSAC | 공지사항 | https://www.kosac.re.kr/menus/270/boards/386/posts |
| KEDI | 입찰공고 | https://www.kedi.re.kr/khome/mobile2/announce/listBidAnnounceForm.do |
| KEDI | 공지사항 | https://www.kedi.re.kr/khome/mobile2/announce/listNoticeAnnounceForm.do |

KOSAC은 한국과학창의재단의 현재 약칭이다(2025년 KOFAC에서 변경, 도메인 `kosac.re.kr`).

## 접속·구조 조사 결과 (2026-09-26, GitHub Actions 미국 러너)

- 모든 게시판이 해외 IP에서 200으로 응답한다. 목록은 서버가 HTML로 그려서 내려준다
- NIPA·KOSAC: 상세 페이지가 일반 링크(`/home/2-1/16839`, `/menus/…/posts/…`)
- NIA·KERIS: 상세 페이지를 `javascript:` 함수로 연다. 함수 인자에서 글 번호를 읽어 상세 주소를 만들어야 한다
- KEDI: 목록 페이지에서 글 목록이 확인되지 않았다. 상세 주소 형식은 `selectAnnounceForm.do?board_sq_no={1 공지|2 입찰}&article_sq_no={글번호}`
- robots.txt: 위 경로를 막는 기관은 없다. NIA는 Googlebot에만 `/site/nia_kor/ex/bbs/`를 막았다. KERIS robots.txt는 요청이 끊겨 확인 불가
- KERIS 공지사항에는 선도교사 양성연수(인공지능, 교실혁명 등) 같은 사업 모집이 함께 올라온다
- KERIS 발주계획은 나라장터 공고라 기존 나라장터 API로 받으면 된다

상세 기록: policy-harvest `docs/research.md`, 조사 스크립트 `probe/probe_sites.py`.

## Policy Fit 세션에 줄 요청문

```
산하기관 공고 게시판을 공고 소스로 추가할지 검토해줘.
대상: NIPA·NIA·KERIS·KOSAC(한국과학창의재단, 구 KOFAC)·KEDI의 입찰공고·사업공고·공지사항 게시판.
게시판 주소와 접속·구조 조사 결과는 opethianist-stack/policy-harvest 레포의 docs/handoff-policy-fit.md에 있어.
- 나라장터 API로 이미 잡히는 입찰공고와 겹치는지 먼저 확인해줘(기관 게시판에만 있는 공고가 얼마나 되는지)
- KERIS 공지사항의 연수 사업 모집처럼 나라장터에 안 올라오는 사업 공지를 어떻게 잡을지 정해줘
- CLAUDE.md의 정책문서 수집 프로젝트 소개에서 KOFAC→KOSAC, KICE 제외, 수집 범위(부처·공공기관 정책문서, 공고 제외)를 고쳐줘
```
