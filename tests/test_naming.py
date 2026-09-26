import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harvest import naming  # noqa: E402


def test_build_and_parse_roundtrip():
    name = naming.build_name("19-12-1", "교육청", "충청남도교육청", "충남교육 주요업무계획", "2026", "pdf")
    assert name == "19-12-1_교육청_충청남도교육청_충남교육 주요업무계획_2026.pdf"
    m = naming.parse_name(name)
    assert (m["id"], m["category"], m["org"], m["title"], m["year"]) == (
        "19-12-1", "교육청", "충청남도교육청", "충남교육 주요업무계획", "2026")
    assert naming.check_name(name) == []


def test_kind_and_cleaning():
    name = naming.build_name("20-1", "부처", "교육부", "AI_인재 양성/방안", "2026", "HWPX", kind="보도")
    assert name == "20-1_부처_교육부_AI 인재 양성 방안_보도_2026.hwpx"


def test_rejects_bad_values():
    with pytest.raises(ValueError):
        naming.build_name("20", "기관", "NIA", "업무계획", "2026", "pdf")
    with pytest.raises(ValueError):
        naming.build_name("20번", "공공기관", "NIA", "업무계획", "2026", "pdf")
    with pytest.raises(ValueError):
        naming.build_name("20", "공공기관", "NIA", "업무계획", "26", "pdf")


def test_check_name_flags_real_mistakes():
    # 분류 칸이 빠진 이름: 기관명이 분류로 읽힌다
    assert "분류 칸이 '충청남도교육청'" in naming.check_name("19-12_충청남도교육청_2026 충남교육 주요업무계획_2026.pdf")
    assert "색인되지 않는 형식(png)" in naming.check_name("19-6_교육청_대전광역시교육청_주요업무계획_2026.pdf.png")


def test_next_group_number():
    names = ["01_부처_a_b_2026.pdf", "18-2_부처_a_b_2025.pdf", "19-12-1_교육청_a_b_2026.pdf", "_policy-harvest.txt"]
    assert naming.next_group_number(names) == 20
