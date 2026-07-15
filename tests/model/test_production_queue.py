"""Pure unit tests for the production-queue formulas and FIFO structure.

PRD.md "생산 라인" formulas (order fixed):
    부족분 = 주문 수량 - 현재 재고
    실 생산량 = ceil(부족분 / 수율)
    총 생산 시간 = 평균 생산시간 * 실 생산량
"""

from sampleordersystem.model.production_queue import (
    ProductionProgress,
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


class FakeClock:
    """A steppable fake clock: starts at 0.0, advances only when told to."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_item(**overrides):
    defaults = dict(
        order_id=1, sample_id=1, quantity=10, shortfall=5, actual_production=6, total_time=10.0
    )
    defaults.update(overrides)
    return ProductionQueueItem(**defaults)


def test_enqueue_into_empty_queue_starts_the_timer_immediately():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    item = make_item(total_time=10.0)

    queue.enqueue(item)

    assert item.started_at == 0.0


def test_enqueue_behind_an_existing_item_leaves_timer_unset():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    front = make_item(order_id=1, total_time=10.0)
    behind = make_item(order_id=2, total_time=5.0)

    queue.enqueue(front)
    clock.advance(3.0)
    queue.enqueue(behind)

    assert front.started_at == 0.0
    assert behind.started_at is None


def test_is_front_ready_false_before_total_time_elapsed():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    queue.enqueue(make_item(total_time=10.0))

    clock.advance(9.0)

    assert queue.is_front_ready() is False


def test_is_front_ready_true_at_or_after_total_time_elapsed():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    queue.enqueue(make_item(total_time=10.0))

    clock.advance(10.0)

    assert queue.is_front_ready() is True


def test_is_front_ready_false_when_queue_empty():
    queue = ProductionQueue(clock=FakeClock())

    assert queue.is_front_ready() is False


def test_remaining_time_decreases_as_clock_advances():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    queue.enqueue(make_item(total_time=10.0))

    assert queue.remaining_time() == 10.0

    clock.advance(4.0)
    assert queue.remaining_time() == 6.0

    clock.advance(6.0)
    assert queue.remaining_time() == 0.0

    clock.advance(100.0)
    assert queue.remaining_time() == 0.0  # clamped, never negative


def test_remaining_time_is_none_when_queue_empty():
    queue = ProductionQueue(clock=FakeClock())

    assert queue.remaining_time() is None


def test_dequeue_starts_the_next_items_timer():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    front = make_item(order_id=1, total_time=10.0)
    behind = make_item(order_id=2, total_time=5.0)
    queue.enqueue(front)
    queue.enqueue(behind)

    clock.advance(10.0)
    assert behind.started_at is None

    dequeued = queue.dequeue()

    assert dequeued is front
    assert behind.started_at == 10.0
    assert queue.remaining_time() == 5.0


def test_front_progress_is_none_when_queue_empty():
    queue = ProductionQueue(clock=FakeClock())

    assert queue.front_progress() is None


def test_front_progress_reports_floor_of_elapsed_fraction():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    item = make_item(actual_production=10, total_time=20.0)
    queue.enqueue(item)

    clock.advance(10.0)  # half of total_time -> avg_per_unit=2.0 -> 5 units

    progress = queue.front_progress()

    assert progress == ProductionProgress(item=item, elapsed=10.0, produced_so_far=5)


def test_front_progress_never_exceeds_actual_production_even_well_past_total_time():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    item = make_item(actual_production=10, total_time=20.0)
    queue.enqueue(item)

    clock.advance(40.0)  # 2x total_time

    progress = queue.front_progress()

    assert progress.produced_so_far == 10
    assert progress.elapsed == 40.0


def test_dequeue_on_now_empty_queue_does_not_crash():
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    queue.enqueue(make_item(total_time=10.0))

    clock.advance(10.0)
    assert queue.dequeue() is not None
    assert queue.dequeue() is None
    assert queue.remaining_time() is None
