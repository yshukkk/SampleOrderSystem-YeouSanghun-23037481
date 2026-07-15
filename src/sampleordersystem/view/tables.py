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
