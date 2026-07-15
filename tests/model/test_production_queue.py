"""Pure unit tests for the production-queue formulas and FIFO structure.

PRD.md "생산 라인" formulas (order fixed):
    부족분 = 주문 수량 - 현재 재고
    실 생산량 = ceil(부족분 / 수율)
    총 생산 시간 = 평균 생산시간 * 실 생산량
"""

from sampleordersystem.model.order import STATUS_PRODUCING, STATUS_RESERVED, OrderRepository
from sampleordersystem.model.production_queue import (
    ProductionProgress,
    ProductionQueue,
    ProductionQueueItem,
    calculate_actual_production,
    calculate_shortfall,
    calculate_total_time,
    rebuild_production_queue,
)
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


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


# --- rebuild_production_queue -----------------------------------------------
#
# `ProductionQueue` is never persisted -- only an order's final
# `status: "PRODUCING"` survives a process restart. These tests simulate a
# restart by building a PRODUCING order directly via `update_status` (never
# enqueued through the live approve flow), then confirm `rebuild_production_queue`
# repopulates a fresh `ProductionQueue` with best-effort-recomputed figures.


def build_repos(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    return sample_repo, order_repo


def make_producing_order(sample_repo, order_repo, sample_id, stock, avg_production_time, yield_rate, quantity, customer_name="고객"):
    sample_repo.register(sample_id, f"시료{sample_id}", avg_production_time, yield_rate)
    if stock:
        sample_repo.add_stock(sample_id, stock)
    order = order_repo.intake(sample_id=sample_id, customer_name=customer_name, quantity=quantity)
    order_repo.update_status(order.id, STATUS_PRODUCING)
    return order


def test_rebuild_restores_a_single_producing_order_with_recomputed_figures(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    order = make_producing_order(
        sample_repo, order_repo, sample_id=1, stock=3, avg_production_time=2.0, yield_rate=0.5, quantity=10
    )
    queue = ProductionQueue(clock=FakeClock())

    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 1
    item = queue.peek()
    assert item.order_id == order.id
    assert item.sample_id == 1
    assert item.quantity == 10
    # shortfall = 10 - 3 = 7; actual_production = ceil(7/0.5) = 14; total_time = 2.0*14 = 28.0
    assert item.shortfall == 7
    assert item.actual_production == 14
    assert item.total_time == 28.0


def test_rebuild_restores_multiple_producing_orders_in_ascending_id_order(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(1, "시료1", 1.0, 1.0)
    sample_repo.register(2, "시료2", 2.0, 0.5)

    order_b = order_repo.intake(sample_id=2, customer_name="B", quantity=5)
    order_repo.update_status(order_b.id, STATUS_PRODUCING)
    order_a = order_repo.intake(sample_id=1, customer_name="A", quantity=3)
    order_repo.update_status(order_a.id, STATUS_PRODUCING)

    queue = ProductionQueue(clock=FakeClock())
    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 2
    # order_b was created first (lower id) even though enqueued second here
    first = queue.dequeue()
    second = queue.dequeue()
    assert first.order_id == order_b.id
    assert second.order_id == order_a.id
    assert queue.dequeue() is None


def test_rebuild_skips_producing_order_whose_sample_no_longer_exists(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(1, "시료1", 1.0, 1.0)
    order = order_repo.intake(sample_id=999, customer_name="고객", quantity=5)
    order_repo.update_status(order.id, STATUS_PRODUCING)

    queue = ProductionQueue(clock=FakeClock())
    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 0


def test_rebuild_clamps_shortfall_to_zero_when_current_stock_already_covers_quantity(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    order = make_producing_order(
        sample_repo, order_repo, sample_id=1, stock=50, avg_production_time=3.0, yield_rate=0.5, quantity=10
    )
    # Simulate stock having since risen (e.g. another completion credited it)
    # past the order's quantity.

    queue = ProductionQueue(clock=FakeClock())
    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 1
    item = queue.peek()
    assert item.order_id == order.id
    assert item.shortfall == 0
    assert item.actual_production == 0
    assert item.total_time == 0.0
    # is_front_ready compares elapsed (>= 0.0) against total_time (0.0) -- with
    # a fake clock frozen at reconstruction time (elapsed=0.0), 0.0 >= 0.0 is
    # already True: a fully-covered restored item is immediately ready, no
    # further time need pass. This is sensible (nothing left to produce), and
    # does not crash or get the queue stuck.
    assert queue.is_front_ready() is True


def test_rebuild_ignores_non_producing_orders(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(1, "시료1", 1.0, 1.0)

    reserved = order_repo.intake(sample_id=1, customer_name="R", quantity=1)
    assert reserved.status == STATUS_RESERVED  # left as-is, never approved

    confirmed = order_repo.intake(sample_id=1, customer_name="C", quantity=1)
    order_repo.update_status(confirmed.id, "CONFIRMED")

    released = order_repo.intake(sample_id=1, customer_name="L", quantity=1)
    order_repo.update_status(released.id, "RELEASED")

    rejected = order_repo.intake(sample_id=1, customer_name="X", quantity=1)
    order_repo.update_status(rejected.id, "REJECTED")

    queue = ProductionQueue(clock=FakeClock())
    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 0


def test_rebuild_against_no_producing_orders_leaves_queue_empty(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(1, "시료1", 1.0, 1.0)
    order_repo.intake(sample_id=1, customer_name="A", quantity=1)  # stays RESERVED

    queue = ProductionQueue(clock=FakeClock())
    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 0


def test_rebuild_against_completely_empty_repositories_does_not_crash(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    queue = ProductionQueue(clock=FakeClock())

    rebuild_production_queue(order_repo, sample_repo, queue)

    assert len(queue) == 0
