"""Integration tests for ProductionController -- driven entirely through fakes.

Phase 5 covers PRD "5. 생산 라인": status/count display, non-destructive
FIFO listing of the production queue, and production-complete processing
(dequeue front item, PRODUCING -> CONFIRMED, credit stock). Completion is
now fully automatic via `drain_ready_items()` (called at the top of every
`run_once()`) -- there is no manual "생산 완료 처리" menu action any more,
so all completion coverage here drives `drain_ready_items()` directly (or
via `run_once()`'s auto-drain), never a menu choice.
"""

from sampleordersystem.controller.production_controller import ProductionController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.production_queue import ProductionQueue, ProductionQueueItem
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


class FakeClock:
    """A steppable fake clock: starts at 0.0, advances only when told to."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeConsole:
    """Supplies canned answers to input() calls and records print() calls."""

    def __init__(self, answers):
        self._answers = iter(answers)
        self.printed = []

    def read(self):
        return next(self._answers)

    def write(self, line):
        self.printed.append(line)

    def printed_text(self):
        return "\n".join(self.printed)


def build_controller(tmp_path, answers, queue=None):
    console = FakeConsole(answers)
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    queue = queue if queue is not None else ProductionQueue()
    controller = ProductionController(
        order_repo, sample_repo, queue, input_func=console.read, output_func=console.write
    )
    return controller, console, sample_repo, order_repo, queue


def make_producing_order(sample_repo, order_repo, *, stock, quantity, yield_rate=0.5, avg_production_time=2.0, sample_id=1):
    """Register a sample, bump its stock (bypassing the always-0 initial
    value the same way test_order_controller.py does, via the underlying
    JsonRepository), then intake+mark an order PRODUCING for it."""
    sample = sample_repo.register(
        id=sample_id, name=f"Wafer-{sample_id}", avg_production_time=avg_production_time, yield_rate=yield_rate
    )
    sample_repo._repository.update(sample.id, stock=stock)
    sample = sample_repo.find(sample.id)
    order = order_repo.intake(sample_id=sample.id, customer_name="홍길동", quantity=quantity)
    order_repo.update_status(order.id, "PRODUCING")
    return sample, order


def test_status_reflects_current_queue_length(tmp_path):
    queue = ProductionQueue()
    queue.enqueue(ProductionQueueItem(order_id=1, sample_id=1, quantity=5, shortfall=3, actual_production=6, total_time=12.0))
    queue.enqueue(ProductionQueueItem(order_id=2, sample_id=1, quantity=5, shortfall=3, actual_production=6, total_time=12.0))
    controller, console, _, _, _ = build_controller(tmp_path, ["1", "3"], queue=queue)

    controller.run_once()

    assert "2" in console.printed_text()


def test_status_shows_in_production_line_with_progress_when_queue_non_empty(tmp_path):
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    queue.enqueue(
        ProductionQueueItem(
            order_id=7, sample_id=3, quantity=10, shortfall=10, actual_production=10, total_time=20.0
        )
    )
    clock.advance(10.0)  # half elapsed -> produced_so_far == 5
    controller, console, _, _, _ = build_controller(tmp_path, ["1", "3"], queue=queue)

    controller.run_once()

    printed = console.printed_text()
    assert "생산 중" in printed
    assert "주문 ID=7" in printed
    assert "시료ID=3" in printed
    assert "목표생산량=10" in printed
    assert "현재까지 생산량=5" in printed


def test_status_omits_in_production_line_when_queue_empty(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["1", "3"])

    controller.run_once()

    printed = console.printed_text()
    assert "생산 중" not in printed
    assert "0" in printed


def test_list_queue_preserves_fifo_order_and_is_non_destructive(tmp_path):
    queue = ProductionQueue()
    queue.enqueue(ProductionQueueItem(order_id=1, sample_id=10, quantity=5, shortfall=2, actual_production=4, total_time=8.0))
    queue.enqueue(ProductionQueueItem(order_id=2, sample_id=20, quantity=7, shortfall=3, actual_production=6, total_time=12.0))
    controller, console, _, _, _ = build_controller(tmp_path, ["2"], queue=queue)

    controller.run_once()

    printed = console.printed_text()
    first_pos = printed.index("1 | 10")
    second_pos = printed.index("2 | 20")
    assert first_pos < second_pos
    assert len(queue) == 2  # listing must not consume the queue


def test_list_queue_when_empty_reports_message_not_crash(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["2"])

    still_running = controller.run_once()

    assert still_running is True
    assert "없습니다" in console.printed_text()


def test_drain_ready_items_dequeues_front_item_only(tmp_path):
    # Auto-drain (the only completion path now that the manual "생산 완료
    # 처리" menu action is gone) must complete just the front item when only
    # it is ready, leaving the second item PRODUCING and still queued.
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, [], queue=queue)
    sample_a, order_a = make_producing_order(
        sample_repo, order_repo, stock=0, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=1
    )
    sample_b, order_b = make_producing_order(
        sample_repo, order_repo, stock=0, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=2
    )
    queue.enqueue(
        ProductionQueueItem(order_id=order_a.id, sample_id=sample_a.id, quantity=5, shortfall=5, actual_production=5, total_time=5.0)
    )
    queue.enqueue(
        ProductionQueueItem(order_id=order_b.id, sample_id=sample_b.id, quantity=5, shortfall=5, actual_production=5, total_time=5.0)
    )
    clock.advance(5.0)

    controller.drain_ready_items()

    assert order_repo.find(order_a.id).status == "CONFIRMED"
    assert order_repo.find(order_b.id).status == "PRODUCING"
    assert len(queue) == 1
    remaining = queue.peek()
    assert remaining.order_id == order_b.id


def test_drain_ready_items_persists_new_fronts_production_started_at(tmp_path):
    # Fix 1: when completing the front item promotes a new item to the
    # front, that new front's real wall-clock `started_at` (just stamped by
    # `ProductionQueue.dequeue()`) must also be persisted onto its order
    # record, so it too survives a restart.
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, [], queue=queue)
    sample_a, order_a = make_producing_order(
        sample_repo, order_repo, stock=0, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=1
    )
    sample_b, order_b = make_producing_order(
        sample_repo, order_repo, stock=0, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=2
    )
    queue.enqueue(
        ProductionQueueItem(order_id=order_a.id, sample_id=sample_a.id, quantity=5, shortfall=5, actual_production=5, total_time=5.0)
    )
    queue.enqueue(
        ProductionQueueItem(order_id=order_b.id, sample_id=sample_b.id, quantity=5, shortfall=5, actual_production=5, total_time=5.0)
    )
    clock.advance(5.0)

    controller.drain_ready_items()

    new_front = queue.peek()
    assert new_front.order_id == order_b.id
    assert new_front.started_at == clock.now  # just stamped by dequeue()

    record = order_repo.find_raw(order_b.id)
    assert record["production_started_at"] == new_front.started_at


def test_drain_ready_items_completes_ready_front_item_directly(tmp_path):
    # Core unit-level proof of the new auto-drain behavior: calling
    # drain_ready_items() directly (not through run_once()/choice "3")
    # completes a ready item and returns a non-empty message list.
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, [], queue=queue)
    sample, order = make_producing_order(sample_repo, order_repo, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0)
    queue.enqueue(
        ProductionQueueItem(
            order_id=order.id, sample_id=sample.id, quantity=10, shortfall=7, actual_production=14, total_time=28.0
        )
    )
    clock.advance(28.0)

    messages = controller.drain_ready_items()

    assert len(messages) == 1
    assert "CONFIRMED" in messages[0]
    updated_order = order_repo.find(order.id)
    assert updated_order.status == "CONFIRMED"
    updated_sample = sample_repo.find(sample.id)
    assert updated_sample.stock == 3 + 14
    assert len(queue) == 0


def test_drain_ready_items_completes_multiple_items_ready_in_one_call(tmp_path):
    # Per the queue's real timer semantics (single production line): the
    # second item's `started_at` is only stamped -- to the *current* clock
    # reading -- once the first item is dequeued (see `ProductionQueue.
    # dequeue`), so it can only *already* be ready at that same instant if
    # its own total_time is 0.0 (nothing left to produce for it, e.g. its
    # shortfall was already fully covered by stock -- a real, unforced case;
    # see test_production_queue.py's "clamps shortfall to zero" test for the
    # same total_time=0.0 scenario). That is the one faithful way two items
    # can both complete within a single drain_ready_items() call without a
    # fake clock ticking forward *during* the call (which no clock here does).
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, [], queue=queue)
    sample_a, order_a = make_producing_order(
        sample_repo, order_repo, stock=0, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=1
    )
    sample_b, order_b = make_producing_order(
        sample_repo, order_repo, stock=5, quantity=5, yield_rate=1.0, avg_production_time=1.0, sample_id=2
    )
    queue.enqueue(
        ProductionQueueItem(order_id=order_a.id, sample_id=sample_a.id, quantity=5, shortfall=5, actual_production=5, total_time=5.0)
    )
    # order_b's stock already covers its quantity -> shortfall/actual_production/
    # total_time are all 0 (mirrors rebuild_production_queue's clamping case).
    queue.enqueue(
        ProductionQueueItem(order_id=order_b.id, sample_id=sample_b.id, quantity=5, shortfall=0, actual_production=0, total_time=0.0)
    )
    clock.advance(5.0)  # item A ready; item B's timer hasn't started yet, but needs 0.0 more once it has

    messages = controller.drain_ready_items()

    assert len(messages) == 2
    assert order_repo.find(order_a.id).status == "CONFIRMED"
    assert order_repo.find(order_b.id).status == "CONFIRMED"
    updated_sample_a = sample_repo.find(sample_a.id)
    updated_sample_b = sample_repo.find(sample_b.id)
    assert updated_sample_a.stock == 5  # 0 + actual_production(5)
    assert updated_sample_b.stock == 5  # 5 + actual_production(0), unchanged
    assert len(queue) == 0


def test_drain_ready_items_on_empty_queue_returns_empty_list_no_state_change(tmp_path):
    controller, console, sample_repo, order_repo, queue = build_controller(tmp_path, [])

    messages = controller.drain_ready_items()

    assert messages == []
    assert len(queue) == 0


def test_drain_ready_items_when_front_not_ready_returns_empty_list_no_state_change(tmp_path):
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, [], queue=queue)
    sample, order = make_producing_order(sample_repo, order_repo, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0)
    queue.enqueue(
        ProductionQueueItem(
            order_id=order.id, sample_id=sample.id, quantity=10, shortfall=7, actual_production=14, total_time=28.0
        )
    )
    clock.advance(10.0)  # not enough yet

    messages = controller.drain_ready_items()

    assert messages == []
    updated_order = order_repo.find(order.id)
    assert updated_order.status == "PRODUCING"
    assert len(queue) == 1


def test_run_once_auto_drains_ready_item_before_menu_choice_is_consumed(tmp_path):
    # run_once() now drains at the very top, before the menu is shown or the
    # choice is read -- so completion happens regardless of which choice is
    # fed. Feeding a harmless choice ("2", list queue) proves the transition
    # was already done by the auto-drain, not by any menu action.
    clock = FakeClock()
    queue = ProductionQueue(clock=clock)
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, ["2"], queue=queue)
    sample, order = make_producing_order(sample_repo, order_repo, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0)
    queue.enqueue(
        ProductionQueueItem(
            order_id=order.id, sample_id=sample.id, quantity=10, shortfall=7, actual_production=14, total_time=28.0
        )
    )
    clock.advance(28.0)

    still_running = controller.run_once()

    assert still_running is True
    updated_order = order_repo.find(order.id)
    assert updated_order.status == "CONFIRMED"
    updated_sample = sample_repo.find(sample.id)
    assert updated_sample.stock == 3 + 14
    assert len(queue) == 0
    assert "CONFIRMED" in console.printed_text()
    # confirms the message came from the auto-drain, printed before the menu
    printed = console.printed_text()
    assert printed.index("CONFIRMED") < printed.index("생산 라인")


def test_exit_option_stops_the_loop(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["3"])

    still_running = controller.run_once()

    assert still_running is False
    assert "돌아갑니다" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
