import datetime
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harvest import collect  # noqa: E402
from harvest.sources import msit  # noqa: E402
from harvest.sources.base import Attachment, pick_attachments  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def test_msit_parse():
    total, posts = msit.parse(json.loads((FIX / "msit_press.json").read_text(encoding="utf-8")), "press")
    assert total == 17555 and len(posts) == 2
    p = posts[0]
    assert p.key == "MSIT:press:3180001"
    assert p.posted_at == "2026-01-15" and p.title == "[보도자료] 2026년 과학기술정보통신부 업무계획 발표"
    # hwpx+odt 쌍은 hwpx만, pdf는 따로 남는다(odt만 있으면 odt를 남겨 저장할 때 PDF로 바꾼다)
    assert sorted(a.name for a in p.attachments) == ["붙임_업무계획.pdf", "업무계획 보도자료.hwpx"]
    # files 가 한 건(객체)인 경우
    assert [a.ext for a in posts[1].attachments] == ["odt"]


def test_msit_key_decoding(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_KEY", "abc%2Bdef%3D%3D")
    assert msit.service_key() == "abc+def=="
    monkeypatch.setenv("DATA_GO_KR_KEY", "abc+def==")
    assert msit.service_key() == "abc+def=="


def test_pick_attachments_prefers_indexed():
    atts = [Attachment("a.odt", "1"), Attachment("A.hwp", "2"), Attachment("A.pdf", "3"), Attachment("b.zip", "4"),
            Attachment("c.odt", "5"), Attachment("c.zip", "6"), Attachment("d.JPG", "7"), Attachment("e.xlsx", "8")]
    assert sorted(a.url for a in pick_attachments(atts)) == ["3", "4", "5", "8"]


def test_msit_keep_window():
    since, today = datetime.date(2026, 9, 14), datetime.date(2026, 9, 28)
    from harvest.sources.base import Post
    mk = lambda kind, d: Post("MSIT", kind, "1", "t", d, "u")
    assert msit.keep(mk("press", "2026-09-14"), since, today.year)
    assert not msit.keep(mk("press", "2026-09-13"), since, today.year)
    assert msit.keep(mk("policy", "2026-01-02"), since, today.year)
    assert not msit.keep(mk("policy", "2025-12-31"), since, today.year)


def test_rows_and_doc_name():
    _, posts = msit.parse(json.loads((FIX / "msit_press.json").read_text(encoding="utf-8")), "press")
    now = datetime.datetime(2026, 9, 28, 9, 0)
    rows = collect.to_rows(posts, collect.load_agencies(), now)
    assert len(rows) == 3
    r = rows[0]
    assert (r["category"], r["org"], r["year"]) == ("부처", "과기정통부", "2026")
    assert r["doc_name"] == "2026년 과학기술정보통신부 업무계획 발표"
    assert set(r) <= set(collect.sheet.FIELDS)


def test_rows_use_classification():
    _, posts = msit.parse(json.loads((FIX / "msit_press.json").read_text(encoding="utf-8")), "press")
    p = posts[0]
    result = {"recommend": "포함", "doc_type": "업무계획", "topics": ["AI", "R&D", "인재", "초과"],
              "doc_name": "과기정통부 업무계획", "year": "2026", "reason": "업무계획 발표",
              "attachments": [{"index": 0, "doc_name": "업무계획 보도자료", "kind": "보도"},
                              {"index": 1, "doc_name": "주요업무 추진계획", "kind": "별첨"}]}
    rows = collect.to_rows([p], collect.load_agencies(), datetime.datetime(2026, 9, 28), {p.key: result})
    by_att = {r["att_name"]: r for r in rows}
    hwpx = next(r for r in rows if r["att_name"].endswith(".hwpx"))
    assert hwpx["recommend"] == "포함" and hwpx["topics"] == ["AI", "R&D", "인재"]
    assert {(r["doc_name"], r["kind"]) for r in rows} == {("업무계획 보도자료", "보도"), ("주요업무 추진계획", "별첨")}


def test_http_retries_connection_errors(monkeypatch):
    import requests
    from harvest.sources import base
    monkeypatch.setattr(base, "RETRY_WAITS", (0, 0))
    calls = []

    def flaky(url, **kw):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectTimeout("timed out")
        return "ok"

    http = base.Http(delay=0)
    monkeypatch.setattr(http.s, "get", flaky)
    assert http.get("u") == "ok" and len(calls) == 3

    def down(url, **kw):
        calls.append(url)
        raise requests.ConnectionError("down")

    calls.clear()
    monkeypatch.setattr(http.s, "get", down)
    with pytest.raises(requests.ConnectionError):
        http.get("u")
    assert len(calls) == 3


def test_nipa_list_and_detail():
    from harvest.sources import nipa
    rows = nipa.parse_list((FIX / "nipa_list.html").read_text(encoding="utf-8"), "/home/4-4-1")
    assert len(rows) == 10
    assert rows[0] == ("16942", "정보통신산업진흥원, 한국엔젤투자협회와 손잡고 스타트업 국내외 양방향 진출 지원 나선다.", "2026-09-21")
    body, atts = nipa.parse_detail((FIX / "nipa_detail.html").read_text(encoding="utf-8"), "https://www.nipa.kr/home/4-4-1/16942")
    assert body.startswith("■ 재외 한인 기술인재")
    assert [a.ext for a in atts] == ["pdf", "zip"]
    assert atts[0].url.startswith("https://www.nipa.kr/comm/getFile?")
    assert not atts[0].name.endswith(")") or "파일크기" not in atts[0].name
    # pdf가 있으면 "보도자료(HWPX)및사진.zip"은 뺀다
    assert [a.ext for a in pick_attachments(atts)] == ["pdf"]


def test_pick_attachments_keeps_zip_without_indexed_copy():
    atts = [Attachment("보도자료(HWPX)및사진.zip", "1"), Attachment("붙임.odt", "2")]
    assert sorted(a.url for a in pick_attachments(atts)) == ["1", "2"]
