"""정책문서 폴더 파일명 규칙.

`번호_분류_기관_문서명[_구분]_연도.확장자` — Policy Fit scripts/build_index.py 의 parse_name 과 같은 규칙.
번호는 `12`, `12-1`, `19-12-1`처럼 맨 앞 숫자가 문서 묶음 번호다.
"""

from __future__ import annotations

import re

INDEXED_EXT = {"pdf", "hwpx", "hwp"}  # Policy Fit 색인이 읽는 형식
CATEGORIES = {"부처", "공공기관", "교육청", "협의체"}
_BAD = re.compile(r'[_\\/:*?"<>|\n\r\t]')


def clean_part(text: str) -> str:
    """파일명 한 칸에 쓸 수 있게 `_`와 금지 문자를 없애고 공백을 줄인다."""
    return re.sub(r"\s+", " ", _BAD.sub(" ", text)).strip()


def build_name(number: str, category: str, org: str, title: str, year: str, ext: str, kind: str = "") -> str:
    if category not in CATEGORIES:
        raise ValueError(f"분류가 규칙에 없습니다: {category}")
    if not re.fullmatch(r"\d+(-\d+)*", number):
        raise ValueError(f"번호 형식이 아닙니다: {number}")
    if not re.fullmatch(r"(19|20)\d{2}", str(year)):
        raise ValueError(f"연도 형식이 아닙니다: {year}")
    parts = [number, category, clean_part(org), clean_part(title)]
    if kind:
        parts.append(clean_part(kind))
    parts.append(str(year))
    if not all(parts):
        raise ValueError(f"빈 칸이 있습니다: {parts}")
    return "_".join(parts) + "." + ext.lower().lstrip(".")


def parse_name(filename: str) -> dict:
    """Policy Fit parse_name 과 같은 방식으로 읽는다(검증용)."""
    stem, _, ext = filename.rpartition(".")
    parts = stem.split("_")
    year = parts[-1] if re.fullmatch(r"(19|20)\d{2}", parts[-1]) else ""
    body = parts[1:-1] if year else parts[1:]
    return {
        "id": parts[0],
        "category": body[0] if body else "",
        "org": body[1] if len(body) > 1 else "",
        "title": " ".join(body[2:]) if len(body) > 2 else stem,
        "year": year,
        "ext": ext.lower(),
    }


def check_name(filename: str) -> list[str]:
    """규칙 위반 목록. 빈 목록이면 통과."""
    problems = []
    m = parse_name(filename)
    if not re.fullmatch(r"\d+(-\d+)*", m["id"]):
        problems.append("번호 형식 아님")
    if m["category"] not in CATEGORIES:
        problems.append(f"분류 칸이 '{m['category']}'")
    if not m["year"]:
        problems.append("연도 칸 없음")
    if m["ext"] not in INDEXED_EXT:
        problems.append(f"색인되지 않는 형식({m['ext']})")
    return problems


def group_number(filename: str) -> int | None:
    m = re.match(r"(\d+)", filename)
    return int(m.group(1)) if m else None


def next_group_number(filenames: list[str]) -> int:
    nums = [n for n in (group_number(f) for f in filenames) if n is not None]
    return max(nums, default=0) + 1
