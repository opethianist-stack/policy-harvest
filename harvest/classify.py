"""게시글 분류(Claude). 추천까지만 하고, 승인은 담당자가 시트에서 한다.

환경변수:
  ANTHROPIC_API_KEY
  CLASSIFY_MODEL   기본 claude-opus-5 (예: claude-haiku-4-5 로 바꿀 수 있다)
"""

from __future__ import annotations

import json
import os

import anthropic

from .sources.base import Post

MODEL = os.environ.get("CLASSIFY_MODEL", "").strip() or "claude-opus-5"
DOC_NAME_MAX = 25
FALLBACK_MODELS = {"claude-opus-5", "claude-opus-5-5", "claude-fable-5-1"}
DOC_TYPES = ["업무계획", "기본계획·종합계획", "시행계획", "경영목표·경영공시", "사업계획", "보도자료", "행사·성과", "기타"]

SYSTEM = """너는 교육·과학기술 분야 정책문서 수집기의 분류 담당이다.
부처·공공기관·시도교육청 게시판에서 모은 글 하나를 받아, 부서 정책문서 폴더에 넣을 만한지 추천하고 파일명에 쓸 값을 제안한다.
최종 판단은 담당자가 하므로, 확신이 없으면 '포함'으로 두고 이유에 불확실한 점을 적는다.

## 포함
- 업무계획·기본계획·종합계획·시행계획·추진계획·방안·전략·로드맵
- 경영목표·경영공시·사업계획·운영 성과보고서·연차보고서·평가 결과
- 정책·사업 발표 보도자료, 그 붙임 계획서
- 행사 개최·결과 보도자료(설명회·포럼·공모전·챌린지 등)
- 공모전·경진대회·챌린지의 개최 안내와 모집요강(참가자를 모집하는 공고라도 포함)

## 제외
- 인사·채용·조직 개편 안내
- 입찰·계약·조달 공고와 결과, 지원사업 참여기업 모집 공고(공모전·경진대회는 포함)
- 장·차관 등의 방문·격려·명절 인사·간담회 참석 같은 동정
- 민원·시설·홈페이지 이용 안내, 사칭 주의 등 단순 공지
- 법령 서식·점검 항목표처럼 정책 내용이 없는 참고 서식

## 파일명 값
- doc_name: 문서 내용을 알 수 있는 짧은 이름. 공백 포함 25자 이내. 기관명·연도·괄호 머리말([보도자료] 등)과 "개최", "추진", "발표" 같은 꼬리말은 빼고, 밑줄(_)과 파일명 금지 문자는 쓰지 않는다. 예: "연구개발사업 종합시행계획", "AI 인재양성 방안", "지역 현안 해결 챌린지"
- 첨부마다 kind(구분)를 정한다: 보도자료 본문이면 "보도", 붙임·별첨 계획서면 "별첨", 요약본이면 "요약", 첨부가 하나뿐이거나 구분이 필요 없으면 ""
- 첨부마다 doc_name을 따로 줄 수 있다. 같은 글의 붙임이 서로 다른 문서라면 각각의 이름을 준다
- year: 문서가 다루는 연도(계획 대상 연도). 모르면 게시 연도

## 출력
- topics: 주제 태그 최대 3개(예: AI교육, 디지털교과서, 교원연수, 연구개발)
- reason: 추천 이유 한 문장
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "recommend": {"type": "string", "enum": ["포함", "제외"]},
        "doc_type": {"type": "string", "enum": DOC_TYPES},
        "topics": {"type": "array", "items": {"type": "string"}},
        "doc_name": {"type": "string"},
        "year": {"type": "string"},
        "reason": {"type": "string"},
        "attachments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "doc_name": {"type": "string"},
                    "kind": {"type": "string"},
                },
                "required": ["index", "doc_name", "kind"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["recommend", "doc_type", "topics", "doc_name", "year", "reason", "attachments"],
    "additionalProperties": False,
}


def describe(post: Post, agency: dict) -> str:
    lines = [
        f"기관: {agency['name']} ({agency['category']})",
        f"게시판: {post.kind}",
        f"제목: {post.title}",
        f"게시일: {post.posted_at}",
    ]
    if post.dept:
        lines.append(f"담당 부서: {post.dept}")
    if post.body:
        lines.append(f"본문(앞부분):\n{post.body[:3000]}")
    lines.append("첨부:")
    for i, a in enumerate(post.attachments):
        lines.append(f"  [{i}] {a.name}")
    return "\n".join(lines)


def classify(client: anthropic.Anthropic, post: Post, agency: dict) -> dict:
    """분류 결과 dict. 실패하면 recommend='검토 필요'와 이유를 돌려준다."""
    params = dict(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        cache_control={"type": "ephemeral"},
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": describe(post, agency)}],
    )
    try:
        if MODEL in FALLBACK_MODELS:
            # 분류는 쉬운 일이라 effort low. 안전 분류기가 거절하면 서버가 다른 모델로 다시 돌린다
            params["output_config"]["effort"] = "low"
            res = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
        else:
            res = client.messages.create(**params)
    except anthropic.APIError as e:
        return failed(f"분류 API 오류: {getattr(e, 'message', e)}", post)
    if res.stop_reason == "refusal":
        return failed("모델이 분류를 거절함", post)
    if res.stop_reason == "max_tokens":
        return failed("분류 응답이 잘림", post)
    text = next((b.text for b in res.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except ValueError:
        return failed("분류 응답이 JSON이 아님", post)
    out["doc_name"] = shorten(out.get("doc_name", ""))
    for a in out.get("attachments", []):
        a["doc_name"] = shorten(a.get("doc_name", ""))
    return out


def shorten(name: str, limit: int = DOC_NAME_MAX) -> str:
    """문서명이 limit자를 넘으면 단어 경계에서 자른다(단어 하나가 길면 글자 기준)."""
    name = " ".join(name.split())
    if len(name) <= limit:
        return name
    cut = name[:limit].rsplit(" ", 1)[0]
    return cut if len(cut) >= limit // 2 else name[:limit]


KIND_DOC_TYPE = {"press": "보도자료", "plan": "업무계획"}


def failed(reason: str, post: Post | None = None) -> dict:
    """분류하지 못한 글. 문서 유형은 게시판으로 정하고(보도자료 게시판이면 보도자료), 문서명은 비워 두면 제목으로 채운다."""
    return {"recommend": "검토 필요", "doc_type": KIND_DOC_TYPE.get(post.kind, "") if post else "", "topics": [],
            "doc_name": "", "year": post.posted_at[:4] if post else "", "reason": reason, "attachments": []}


def client() -> anthropic.Anthropic:
    # 과부하(529)·속도 제한은 SDK가 지수 대기로 다시 보낸다. 기본 2회로는 몰릴 때 모자라 늘린다
    return anthropic.Anthropic(max_retries=8)
