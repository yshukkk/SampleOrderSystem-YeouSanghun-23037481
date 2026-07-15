"""Pure string-formatting helpers for rendering Sample tables.

Every function here is a plain function of its arguments -- no printing,
no state, no decisions about *what* to show, only *how* to render it.
"""

from dataclasses import dataclass

from sampleordersystem.model.order import Order
from sampleordersystem.model.production_queue import ProductionProgress, ProductionQueueItem
from sampleordersystem.model.sample import Sample

EMPTY_SAMPLE_LIST_MESSAGE = "등록된 시료가 없습니다."
EMPTY_ORDER_LIST_MESSAGE = "표시할 주문이 없습니다."
EMPTY_PRODUCTION_QUEUE_MESSAGE = "생산 대기 중인 항목이 없습니다."
EMPTY_STOCK_STATUS_MESSAGE = "등록된 시료가 없습니다."

# Order-count-by-status categories shown on the monitoring screen, in display
# order. REJECTED is deliberately absent from this tuple -- PRD 4. 모니터링
# excludes it explicitly, and since `render_order_status_counts_table` only
# ever iterates this tuple to build rows, REJECTED can never appear as a row
# no matter what `counts` dict the caller passes in.
ORDER_STATUS_CATEGORIES = ("RESERVED", "CONFIRMED", "PRODUCING", "RELEASED")

STOCK_STATUS_SUFFICIENT = "여유"
STOCK_STATUS_SHORT = "부족"
STOCK_STATUS_DEPLETED = "고갈"


def render_sample_table(samples: list[Sample]) -> str:
    """Render a list of samples as a simple table, including stock, or a placeholder message."""
    if not samples:
        return EMPTY_SAMPLE_LIST_MESSAGE

    rows = ["ID | 이름 | 평균생산시간 | 수율 | 재고", "-------------------------------------"]
    for sample in samples:
        rows.append(
            f"{sample.id} | {sample.name} | {round(sample.avg_production_time, 2)} | "
            f"{round(sample.yield_rate, 2)} | {sample.stock}"
        )
    return "\n".join(rows)


def render_order_table(orders: list[Order]) -> str:
    """Render a list of orders as a simple table, or a placeholder message.

    Used by "접수된 주문 목록" (RESERVED+PRODUCING, filtered by the caller
    before this function ever sees the list -- this function itself renders
    whatever list it is given, with no status filtering of its own) and by
    the shipping screen's CONFIRMED-only listing.
    """
    if not orders:
        return EMPTY_ORDER_LIST_MESSAGE

    rows = ["ID | 시료ID | 고객명 | 수량 | 상태", "-------------------------------------"]
    for order in orders:
        rows.append(
            f"{order.id} | {order.sample_id} | {order.customer_name} | "
            f"{order.quantity} | {order.status}"
        )
    return "\n".join(rows)


def render_production_queue_table(items: list[ProductionQueueItem]) -> str:
    """Render the production queue's contents, FIFO/enqueue order preserved.

    `items` is expected to already be in FIFO order (front-of-queue first) --
    this function does no sorting or filtering of its own, only rendering.
    """
    if not items:
        return EMPTY_PRODUCTION_QUEUE_MESSAGE

    rows = [
        "주문번호 | 시료ID | 주문량 | 부족분 | 실생산량 | 총생산시간",
        "-------------------------------------------------------",
    ]
    for item in items:
        rows.append(
            f"{item.order_id} | {item.sample_id} | {item.quantity} | "
            f"{item.shortfall} | {item.actual_production} | {round(item.total_time, 2)}"
        )
    return "\n".join(rows)


def render_production_status(count: int, progress: ProductionProgress | None) -> str:
    """Render the "생산 라인 현황" screen: backlog count + front item progress.

    Always shows the backlog count line. When `progress` is not None (i.e.
    something is actively in production), an additional line shows that
    item's order/sample id, target 실생산량, and 현재까지 생산량 -- when
    `progress` is None (empty queue), that second line is simply omitted,
    never fabricated.
    """
    lines = [f"생산 라인 대기 중인 항목 수: {count}"]
    if progress is not None:
        lines.append(
            "생산 중: 주문 ID={order_id} 시료ID={sample_id} 목표생산량={actual_production} "
            "현재까지 생산량={produced_so_far}".format(
                order_id=progress.item.order_id,
                sample_id=progress.item.sample_id,
                actual_production=progress.item.actual_production,
                produced_so_far=progress.produced_so_far,
            )
        )
    return "\n".join(lines)


def render_order_status_counts_table(counts: dict) -> str:
    """Render the monitoring screen's "주문량 확인" view: one row per status.

    Iterates only `ORDER_STATUS_CATEGORIES` (RESERVED/CONFIRMED/PRODUCING/
    RELEASED) regardless of what keys `counts` happens to contain -- REJECTED
    (or any other status) in `counts` is silently ignored and never rendered,
    per PRD "REJECTED는 유효한 주문이 아니므로 이 화면에서 제외". A missing
    category in `counts` renders as 0, not a crash.
    """
    rows = ["상태 | 주문 수", "----------------"]
    for status in ORDER_STATUS_CATEGORIES:
        rows.append(f"{status} | {counts.get(status, 0)}")
    return "\n".join(rows)


@dataclass
class StockStatusRow:
    """One row of the "재고량 확인" view: a sample plus its computed status label."""

    sample: Sample
    status_label: str


def render_stock_status_table(rows: list[StockStatusRow]) -> str:
    """Render the monitoring screen's "재고량 확인" view: one row per sample.

    `rows` is expected to already carry each sample's computed status label
    (여유/부족/고갈) -- this function does no classification of its own, only
    rendering, matching this module's convention of pure rendering functions
    with filtering/classification left to the caller.
    """
    if not rows:
        return EMPTY_STOCK_STATUS_MESSAGE

    lines = ["ID | 이름 | 재고 | 상태", "-------------------------------------"]
    for row in rows:
        lines.append(f"{row.sample.id} | {row.sample.name} | {row.sample.stock} | {row.status_label}")
    return "\n".join(lines)


def render_summary_line(sample_count: int, order_count: int, production_queue_waiting: int) -> str:
    """Render the main-menu summary line: sample/active-order counts + queue backlog.

    `order_count` is expected to already be filtered to active (non-terminal)
    orders by the caller -- RELEASED/REJECTED orders are excluded, since a
    finished order isn't meaningful "load" on the system from this summary's
    point of view.
    """
    return f"등록 시료 수: {sample_count} | 전체 주문 수: {order_count} | 생산라인 대기: {production_queue_waiting}"
