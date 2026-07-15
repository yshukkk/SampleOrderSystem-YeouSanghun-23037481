"""Pure string-formatting helpers for the Sample management console menu.

No printing, no state -- just formatting.
"""

_MENU_LINES = (
    "1. 시료 등록",
    "2. 시료 목록 조회",
    "3. 시료 검색",
    "4. 종료",
)


def render_sample_menu() -> str:
    """Return the full sample-management menu text, ending in a prompt."""
    header = "----- 시료 관리 -----"
    body = "\n".join(_MENU_LINES)
    return f"{header}\n{body}\n번호를 선택하세요: "
