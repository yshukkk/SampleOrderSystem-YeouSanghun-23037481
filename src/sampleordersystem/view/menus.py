"""Pure string-formatting helpers for the Sample management console menu.

No printing, no state -- just formatting.
"""

_MENU_LINES = (
    "1. 시료 등록",
    "2. 시료 목록 조회",
    "3. 시료 검색",
    "4. 뒤로가기",
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
    "2. 접수된 주문 목록",
    "3. 주문 승인",
    "4. 주문 거절",
    "5. 뒤로가기",
)


def render_order_menu() -> str:
    """Return the full order menu text, ending in a prompt.

    Phase 4 adds approval/rejection and the RESERVED+PRODUCING listing on
    top of Phase 3's intake; production-line/shipping/monitoring are later
    phases.
    """
    header = "----- 주문 (접수/승인/거절) -----"
    body = "\n".join(_ORDER_MENU_LINES)
    return f"{header}\n{body}\n번호를 선택하세요: "


def render_intake_guide() -> str:
    """Return the input-order guide line shown when intaking an order."""
    return "(주문 접수 입력 순서: 시료 ID -> 고객명 -> 주문 수량)"


def render_approval_guide() -> str:
    """Return the input-format guide shown just before reading an order id to approve."""
    return "(승인할 주문 번호를 입력하세요)"


def render_rejection_guide() -> str:
    """Return the input-format guide shown just before reading an order id to reject."""
    return "(거절할 주문 번호를 입력하세요)"


_PRODUCTION_MENU_LINES = (
    "1. 생산 라인 현황",
    "2. 대기 주문 확인",
    "3. 뒤로가기",
)


def render_production_menu() -> str:
    """Return the full production-line menu text, ending in a prompt."""
    header = "----- 생산 라인 -----"
    body = "\n".join(_PRODUCTION_MENU_LINES)
    return f"{header}\n{body}\n번호를 선택하세요: "


def render_shipping_header() -> str:
    """Return the "출고 처리" screen header, shown before the CONFIRMED list.

    There is no numbered menu here (see `render_shipping_prompt`) -- every
    call to the shipping screen auto-shows the CONFIRMED order list, so this
    is just a header line preceding that table.
    """
    return "----- 출고 처리 -----"


def render_shipping_prompt() -> str:
    """Return the prompt shown after the CONFIRMED list, ending in a prompt.

    `0` is the documented sentinel for "뒤로가기" (back to the main menu,
    shipping nothing); any other input is parsed as an order id to ship.
    """
    return "출고할 주문 번호를 입력하세요 (뒤로가기: 0): "


_MONITORING_MENU_LINES = (
    "1. 주문량 확인",
    "2. 재고량 확인",
    "3. 뒤로가기",
)


def render_monitoring_menu() -> str:
    """Return the full monitoring menu text, ending in a prompt."""
    header = "----- 모니터링 -----"
    body = "\n".join(_MONITORING_MENU_LINES)
    return f"{header}\n{body}\n번호를 선택하세요: "


def render_main_menu(summary: str) -> str:
    """Return the full main-menu text (with a summary line), ending in a prompt."""
    header = "----- SampleOrderSystem 메인 메뉴 -----"
    body = "\n".join(
        (
            "1. 시료 관리",
            "2. 주문 (접수/승인/거절)",
            "3. 생산 라인",
            "4. 출고 처리",
            "5. 모니터링",
            "6. 종료",
        )
    )
    return f"{header}\n{summary}\n{body}\n번호를 선택하세요: "
