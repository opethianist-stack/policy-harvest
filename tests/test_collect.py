import datetime
import json
import os
import sys
from pathlib import Path

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
