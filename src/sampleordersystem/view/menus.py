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


def render_registration_guide() -> str:
    """Return the input-order guide line shown when registering a sample."""
    return "(시료 등록 입력 순서: ID -> 이름 -> 평균 생산시간 -> 수율)"


def render_search_guide() -> str:
    """Return the input-format guide line shown when searching for samples."""
    return "(시료 검색 입력 형식: 'ID: <숫자>' 또는 '이름: <검색어>')"


_ORDER_MENU_LINES = (
    "1. 주문 접수",
    "2. 종료",
)


def render_order_menu() -> str:
    """Return the full order-intake menu text, ending in a prompt.

    Phase 3 only offers intake; approval/rejection are later phases.
    """
    header = "----- 주문 (접수) -----"
    body = "\n".join(_ORDER_MENU_LINES)
    return f"{header}\n{body}\n번호를 선택하세요: "


def render_main_menu(summary: str) -> str:
    """Return the full main-menu text (with a summary line), ending in a prompt."""
    header = "----- SampleOrderSystem 메인 메뉴 -----"
    body = "\n".join(
        (
            "1. 시료 관리",
            "2. 주문 (접수)",
            "3. 종료",
        )
    )
    return f"{header}\n{summary}\n{body}\n번호를 선택하세요: "
