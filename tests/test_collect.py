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


def test_kosac_list_and_detail():
    from harvest.sources import kosac
    rows = kosac.parse_list((FIX / "kosac_list.html").read_text(encoding="utf-8"), "/menus/272/boards/394/posts")
    assert rows == [("62038", "재단, 인공지능 협업을 위한 업무협약 체결", "2026-08-14"),
                    ("61990", "「2026년 청소년 과학대장정」발대식 개최", "2026-07-28")]
    date, body, atts = kosac.parse_detail((FIX / "kosac_detail.html").read_text(encoding="utf-8"))
    assert date == "2026-07-28" and body.startswith("[기사요약]")
    assert [(a.name, a.ext) for a in atts] == [("[보도자료] 「2026년 청소년 과학대장정」 발대식 개최.pdf", "pdf")]
    assert atts[0].url == "https://cdn.kosac.re.kr/files/cms/attach/202607/639b7ca0116348ac8bf82e72c953d4cb_1785227534435.pdf"


EDU_ICE = """<ul>
<li><a href="javascript:;" data-id="3309500" class="nttInfoBtn"><div class="txt"><p class="tit">2026년 인천교육계획</p></div></a>
  <div><a href="https://ebook/251231/" class="btn_bl">E-book 보기</a>
  <a href="javascript:goFileDown('5eccb8ac844d091f4c83b4df57fc21b7');" class="btn_blL">PDF 다운로드</a></div></li>
<li><a href="javascript:;" data-id="3309417" class="nttInfoBtn"><div class="txt"><p class="tit">2025년 인천교육계획</p></div></a>
  <div><a href="javascript:goFileDown('61e448ca7d6e42cb0525e2cd0f39f651');" class="btn_blL">PDF 다운로드</a></div></li>
</ul>"""

EDU_GNE = """<table class="tb1"><tr><th>글번호</th><th>표지</th><th>내용</th><th>자료받기</th></tr>
<tr><td>4</td><td></td><td>2026 경남교육 등록일 : 2026-01-26</td><td><a href="/component/file/ND_fileDownload.do?q_fileSn=181567067&amp;q_fileId=fab5">PDF</a></td></tr>
<tr><td>3</td><td></td><td>2025 경남교육 등록일 : 2025-03-31</td><td><a href="/component/file/ND_fileDownload.do?q_fileSn=181532831&amp;q_fileId=a407">PDF</a></td></tr>
</table>"""

EDU_GBE = """<title>경상북도교육청-경북교육2026</title>
<a href="/main/cf/fileDownload.do?fileKey=e222516e166c749cc7c6222205dcf514&mi=17868">PDF 다운로드</a>
<a href="/main/cf/fileDownload.do?fileKey=31cc184216aef104b481a297a889ec67   ">PDF 파일받기</a>"""


def test_edu_find_link():
    from harvest.sources import edu
    plans = {o["id"]: o["plan"] for o in edu.offices()}
    assert set(plans) == {"PEN", "ICE", "USE", "GOE", "GWE", "CBE", "JBE", "GBE", "GNE"}
    assert edu.find_link(EDU_ICE, "https://www.ice.go.kr/x", plans["ICE"], 2026) == \
        "https://www.ice.go.kr/comm/nttFileDownload.do?fileKey=5eccb8ac844d091f4c83b4df57fc21b7"
    assert edu.find_link(EDU_ICE, "https://www.ice.go.kr/x", plans["ICE"], 2027) is None
    assert edu.find_link(EDU_GNE, "https://www.gne.go.kr/user/bbs/x", plans["GNE"], 2026) == \
        "https://www.gne.go.kr/component/file/ND_fileDownload.do?q_fileSn=181567067&q_fileId=fab5"
    assert edu.find_link(EDU_GBE, "https://www.gbe.kr/main/x", plans["GBE"], 2026) == \
        "https://www.gbe.kr/main/cf/fileDownload.do?fileKey=31cc184216aef104b481a297a889ec67"
    gwe = '<a href="/cmm/fileDown.do?encKey=MTEyMzE4&amp;type=fileMng" title="2026년 주요업무계획 새창 다운로드 받기">다운로드</a>'
    assert edu.find_link(gwe, "https://www.gwe.go.kr/main/x", plans["GWE"], 2026) == \
        "https://www.gwe.go.kr/cmm/fileDown.do?encKey=MTEyMzE4&type=fileMng"
    assert edu.find_link(gwe, "https://www.gwe.go.kr/main/x", plans["GWE"], 2027) is None
    # 페이지에 대상 연도가 없으면 고르지 않는다(작년 페이지가 그대로 남은 경우)
    assert edu.find_link(EDU_GBE, "https://www.gbe.kr/main/x", plans["GBE"], 2027) is None


def test_edu_rows_carry_fixed_number():
    from harvest.sources import edu
    from harvest.sources.base import Post
    agencies = collect.load_agencies()
    p = Post("CBE", "plan", "2026", "2026 주요업무계획", "2026-01-01", "u", attachments=[Attachment("주요업무계획.pdf", "f")])
    now = datetime.datetime(2026, 9, 28, 9, 0)
    [row] = collect.to_rows([p], agencies, now, {p.key: edu.result(agencies["CBE"], "2026")})
    assert (row["file_no"], row["org"], row["doc_name"], row["year"], row["recommend"]) == \
        ("19-11", "충청북도교육청", "주요업무계획", "2026", "포함")
    assert edu.target_year(datetime.date(2026, 12, 1)) == 2027 and edu.target_year(datetime.date(2027, 2, 1)) == 2027


def test_nia_list_and_detail():
    from harvest.sources import nia
    rows = nia.parse_list((FIX / "nia_list.html").read_text(encoding="utf-8"), "99835")
    assert rows[0] == ("29538", "한국지능정보사회진흥원 직원 사칭 및 물품 발주·개인정보 요구 등에 대한 주의 안내", "2026-06-15")
    assert rows[3] == ("29999", "양자 테스트베드 – 양자인터넷 회선 지원 이용기관 모집", "2026-09-17")
    body, atts = nia.parse_detail((FIX / "nia_detail.html").read_text(encoding="utf-8"), "https://www.nia.or.kr/x")
    assert body.startswith("「2026 국민행복 IT 경진대회」")
    assert [a.ext for a in atts] == ["hwpx", "pdf"]  # 같은 파일 링크가 두 번 나와도 한 번만
    assert [a.ext for a in pick_attachments(atts)] == ["pdf"]


def test_keris_list_and_detail():
    from harvest.sources import keris
    rows = keris.parse_list((FIX / "keris_list.html").read_text(encoding="utf-8"))
    assert rows[1] == ("43888", "[기간 연장] 2026년 학생대상 안전한 개인정보 보호 사례 공모전(~10/11)", "2026-09-15")
    body, atts = keris.parse_detail((FIX / "keris_detail.html").read_text(encoding="utf-8"), "https://www.keris.or.kr/x")
    assert atts[0].name == "260915_[KERIS 보도자료] 대한민국 교육정보화 30년, 에듀넷과 함께 미래교육을 그리다.hwp"
    assert atts[0].url.startswith("https://www.keris.or.kr/common/nttFileDownload.do?fileKey=")
    assert [a.ext for a in pick_attachments(atts)] == ["hwp"]  # 행사 사진은 뺀다


def test_collect_board_skips_pinned_and_stops_on_last_row():
    from harvest.sources.base import collect_board

    class Res:
        def __init__(self, text=""):
            self.text = text

        def raise_for_status(self):
            pass

    pages = {1: [("9", "고정 옛 글", "2025-11-24"), ("30", "새 글", "2026-09-20"), ("29", "새 글2", "2026-09-10")],
             2: [("9", "고정 옛 글", "2025-11-24"), ("28", "옛 글", "2026-08-01")]}
    calls = []

    class FakeHttp:
        def get(self, url, params=None):
            calls.append((url, params))
            return Res(str(params["p"]) if params else "")

    posts = collect_board(FakeHttp(), "X", "notice", "L", lambda p: {"p": p}, lambda html: pages[int(html)],
                          lambda no: f"D{no}", lambda html, url: ("", [Attachment("a.pdf", "u")]),
                          datetime.date(2026, 9, 1), max_pages=5)
    assert [p.post_id for p in posts] == ["30", "29"]
    assert [c for c in calls if c[1]] == [("L", {"p": 1}), ("L", {"p": 2})]  # 2쪽 마지막 행이 기간 밖이라 멈춤


def test_edu_one_office_failure_does_not_stop_others(monkeypatch):
    import requests
    from harvest.sources import edu

    class Res:
        def __init__(self, url, text):
            self.url, self.text = url, text

        def raise_for_status(self):
            pass

    class FakeHttp:
        def get(self, url, **kw):
            if "cbe.go.kr" in url:
                raise requests.ConnectTimeout("timed out")
            return Res(url, "")  # 링크가 없는 페이지

    posts = edu.collect(FakeHttp(), datetime.date(2026, 9, 14), datetime.date(2026, 9, 28))
    assert [p.agency for p in posts] == ["GOE"]  # 주소를 적어 둔 경기만 남고, 충북 실패로 멈추지 않는다
