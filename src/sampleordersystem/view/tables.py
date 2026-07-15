"""Pure string-formatting helpers for rendering Sample tables.

Every function here is a plain function of its arguments -- no printing,
no state, no decisions about *what* to show, only *how* to render it.
"""

from sampleordersystem.model.order import Order
from sampleordersystem.model.production_queue import ProductionQueueItem
from sampleordersystem.model.sample import Sample

EMPTY_SAMPLE_LIST_MESSAGE = "등록된 시료가 없습니다."
EMPTY_ORDER_LIST_MESSAGE = "표시할 주문이 없습니다."
EMPTY_PRODUCTION_QUEUE_MESSAGE = "생산 대기 중인 항목이 없습니다."


def render_sample_table(samples: list[Sample]) -> str:
    """Render a list of samples as a simple table, including stock, or a placeholder message."""
    if not samples:
        return EMPTY_SAMPLE_LIST_MESSAGE

    rows = ["ID | 이름 | 평균생산시간 | 수율 | 재고", "-------------------------------------"]
    for sample in samples:
        rows.append(
            f"{sample.id} | {sample.name} | {sample.avg_production_time} | "
            f"{sample.yield_rate} | {sample.stock}"
        )
    return "\n".join(rows)


def render_order_table(orders: list[Order]) -> str:
    """Render a list of orders as a simple table, or a placeholder message.

    Used by "접수된 주문 목록" (RESERVED-only, filtered by the caller before
    this function ever sees the list -- this function itself renders
    whatever list it is given, with no status filtering of its own).
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
            f"{item.shortfall} | {item.actual_production} | {item.total_time}"
        )
    return "\n".join(rows)


def render_summary_line(
    sample_count: int, total_stock: int, order_count: int, production_queue_waiting: int
) -> str:
    """Render the main-menu summary line: sample/stock/order counts + queue backlog.

    `production_queue_waiting` is always 0 at this phase since the production
    queue itself (Phase 4+) does not exist yet -- kept as an explicit
    parameter so callers stay honest about that once it does.
    """
    return (
        f"등록 시료 수: {sample_count} | 총 재고: {total_stock} | "
        f"전체 주문 수: {order_count} | 생산라인 대기: {production_queue_waiting}"
    )
