"""Pure unit tests for the production-queue formulas and FIFO structure.

PRD.md "생산 라인" formulas (order fixed):
    부족분 = 주문 수량 - 현재 재고
    실 생산량 = ceil(부족분 / 수율)
    총 생산 시간 = 평균 생산시간 * 실 생산량
"""

from sampleordersystem.model.production_queue import (
    ProductionQueue,
    ProductionQueueItem,
    calculate_actual_production,
    calculate_shortfall,
    calculate_total_time,
)


def test_calculate_shortfall_is_quantity_minus_stock():
    assert calculate_shortfall(quantity=10, stock=3) == 7


def test_calculate_shortfall_with_larger_examples():
    assert calculate_shortfall(quantity=100, stock=40) == 60


def test_calculate_actual_production_rounds_up_when_division_is_exact():
    # shortfall=9, yield_rate=0.3 -> 9/0.3 = 30.0 exactly -> ceil = 30
    assert calculate_actual_production(shortfall=9, yield_rate=0.3) == 30


def test_calculate_actual_production_rounds_up_when_division_is_not_exact():
    # shortfall=10, yield_rate=0.3 -> 10/0.3 = 33.333... -> ceil = 34 (not 33)
    assert calculate_actual_production(shortfall=10, yield_rate=0.3) == 34


def test_calculate_total_time_is_avg_time_times_actual_production():
    assert calculate_total_time(avg_production_time=2.5, actual_production=34) == 85.0


def test_production_queue_starts_empty():
    queue = ProductionQueue()

    assert len(queue) == 0
    assert queue.peek() is None
    assert queue.dequeue() is None


def test_production_queue_is_fifo_not_reordered():
    queue = ProductionQueue()
    item_a = ProductionQueueItem(
        order_id=1, sample_id=1, quantity=10, shortfall=5, actual_production=6, total_time=6.0
    )
    item_b = ProductionQueueItem(
        order_id=2, sample_id=1, quantity=20, shortfall=15, actual_production=17, total_time=17.0
    )
    item_c = ProductionQueueItem(
        order_id=3, sample_id=2, quantity=1, shortfall=1, actual_production=2, total_time=2.0
    )

    queue.enqueue(item_a)
    queue.enqueue(item_b)
    queue.enqueue(item_c)

    assert len(queue) == 3
    assert queue.peek() is item_a
    assert queue.dequeue() is item_a
    assert queue.dequeue() is item_b
    assert queue.dequeue() is item_c
    assert queue.dequeue() is None
    assert len(queue) == 0
