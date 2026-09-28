import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic  # noqa: E402

from harvest import classify  # noqa: E402
from harvest.sources.base import Attachment, Post  # noqa: E402

AGENCY = {"name": "과학기술정보통신부", "category": "부처"}
POST = Post("MSIT", "press", "1", "2026년 업무계획 발표", "2026-01-15", "u", dept="기획재정담당관",
            attachments=[Attachment("보도자료.hwpx", "a"), Attachment("붙임.pdf", "b")])
OK = {"recommend": "포함", "doc_type": "업무계획", "topics": ["R&D"], "doc_name": "업무계획", "year": "2026",
      "reason": "업무계획", "attachments": [{"index": 0, "doc_name": "업무계획", "kind": "보도"}]}


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return self.response


def fake_client(response=None, error=None):
    m = FakeMessages(response, error)
    return SimpleNamespace(messages=m, beta=SimpleNamespace(messages=m)), m


def resp(text, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])


def test_describe_lists_attachments():
    d = classify.describe(POST, AGENCY)
    assert "제목: 2026년 업무계획 발표" in d and "[1] 붙임.pdf" in d


def test_classify_parses_json_and_sends_schema():
    c, m = fake_client(resp(json.dumps(OK, ensure_ascii=False)))
    assert classify.classify(c, POST, AGENCY) == OK
    kw = m.calls[0]
    assert kw["output_config"]["format"]["schema"] is classify.SCHEMA
    if classify.MODEL in classify.FALLBACK_MODELS:
        assert kw["fallbacks"] == "default" and kw["output_config"]["effort"] == "low"


def test_shorten_doc_name():
    assert classify.shorten("연구개발사업 종합시행계획") == "연구개발사업 종합시행계획"
    long = "반도체 연구시설 맞춤형 안전 지원 및 현장 점검 추진"
    out = classify.shorten(long)
    assert len(out) <= 25 and long.startswith(out) and not out.endswith(" ")
    assert len(classify.shorten("가" * 40)) == 25


def test_classify_shortens_names():
    long = dict(OK, doc_name="반도체 연구시설 맞춤형 안전 지원 및 현장 점검 추진 계획",
                attachments=[{"index": 0, "doc_name": "가" * 30, "kind": "보도"}])
    c, _ = fake_client(resp(json.dumps(long, ensure_ascii=False)))
    out = classify.classify(c, POST, AGENCY)
    assert len(out["doc_name"]) <= 25 and len(out["attachments"][0]["doc_name"]) == 25


def test_classify_failures_become_review():
    for r in (resp("", stop="refusal"), resp("{", stop="max_tokens"), resp("not json")):
        c, _ = fake_client(r)
        assert classify.classify(c, POST, AGENCY)["recommend"] == "검토 필요"
    err = anthropic.APIConnectionError(request=SimpleNamespace(method="POST", url="x"))
    c, _ = fake_client(error=err)
    out = classify.classify(c, POST, AGENCY)
    assert out["recommend"] == "검토 필요" and "분류 API 오류" in out["reason"]
