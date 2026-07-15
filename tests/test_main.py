"""Tests for `__main__.render_summary`'s active-order-count filtering."""

from sampleordersystem.__main__ import render_summary
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


def build_repos(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    return sample_repo, order_repo


def test_render_summary_excludes_released_and_rejected_orders(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample = sample_repo.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=0.9)

    reserved = order_repo.intake(sample_id=sample.id, customer_name="A", quantity=1)
    confirmed = order_repo.intake(sample_id=sample.id, customer_name="B", quantity=1)
    order_repo.update_status(confirmed.id, "CONFIRMED")
    producing = order_repo.intake(sample_id=sample.id, customer_name="C", quantity=1)
    order_repo.update_status(producing.id, "PRODUCING")
    released = order_repo.intake(sample_id=sample.id, customer_name="D", quantity=1)
    order_repo.update_status(released.id, "RELEASED")
    rejected = order_repo.intake(sample_id=sample.id, customer_name="E", quantity=1)
    order_repo.update_status(rejected.id, "REJECTED")

    assert reserved.status == "RESERVED"  # sanity: intake defaults to RESERVED

    summary = render_summary(sample_repo, order_repo, production_queue_waiting=0)

    assert "전체 주문 수: 3" in summary  # RESERVED + CONFIRMED + PRODUCING only


def test_render_summary_does_not_mention_total_stock(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=0.9)

    summary = render_summary(sample_repo, order_repo, production_queue_waiting=0)

    assert "총 재고" not in summary
