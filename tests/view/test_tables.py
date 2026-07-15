"""Tests for the pure summary-line renderer in `view/tables.py`."""

from sampleordersystem.view.tables import render_summary_line


def test_render_summary_line_does_not_mention_total_stock():
    line = render_summary_line(sample_count=3, order_count=2, production_queue_waiting=1)

    assert "총 재고" not in line


def test_render_summary_line_includes_all_three_counts():
    line = render_summary_line(sample_count=3, order_count=2, production_queue_waiting=1)

    assert "등록 시료 수: 3" in line
    assert "전체 주문 수: 2" in line
    assert "생산라인 대기: 1" in line
