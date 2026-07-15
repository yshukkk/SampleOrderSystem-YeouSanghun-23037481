"""Tests for the pure summary-line renderer in `view/tables.py`."""

from sampleordersystem.model.production_queue import ProductionQueueItem
from sampleordersystem.model.sample import Sample
from sampleordersystem.view.tables import (
    render_production_queue_table,
    render_sample_table,
    render_summary_line,
)


def test_render_summary_line_does_not_mention_total_stock():
    line = render_summary_line(sample_count=3, order_count=2, production_queue_waiting=1)

    assert "총 재고" not in line


def test_render_summary_line_includes_all_three_counts():
    line = render_summary_line(sample_count=3, order_count=2, production_queue_waiting=1)

    assert "등록 시료 수: 3" in line
    assert "전체 주문 수: 2" in line
    assert "생산라인 대기: 1" in line


def test_render_sample_table_rounds_floating_point_noise_in_avg_production_time():
    # Fix 3: a value like 1.2000000000000002 (real float-math noise, e.g.
    # from repeated additions) must render as the clean "1.2", not with
    # trailing noise.
    noisy_time = 0.1 + 1.1  # == 1.2000000000000002 in real float math
    assert noisy_time != 1.2  # sanity: this really is noisy in raw form
    sample = Sample(id=1, name="Wafer-A", avg_production_time=noisy_time, yield_rate=0.9, stock=0)

    table = render_sample_table([sample])

    assert "1.2000000000000002" not in table
    assert "1.2" in table


def test_render_production_queue_table_rounds_floating_point_noise_in_total_time():
    noisy_total_time = 0.1 + 0.1 + 0.1 - 0.3 + 0.45  # noisy float math near 0.45
    item = ProductionQueueItem(
        order_id=1,
        sample_id=1,
        quantity=10,
        shortfall=5,
        actual_production=6,
        total_time=noisy_total_time,
    )

    table = render_production_queue_table([item])

    assert "9999999999999996" not in table
    assert "0.45" in table
