"""Pure string-formatting helpers for rendering Sample tables.

Every function here is a plain function of its arguments -- no printing,
no state, no decisions about *what* to show, only *how* to render it.
"""

from sampleordersystem.model.sample import Sample

EMPTY_SAMPLE_LIST_MESSAGE = "등록된 시료가 없습니다."


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
