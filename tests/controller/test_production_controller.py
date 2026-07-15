"""Integration tests for ProductionController -- driven entirely through fakes.

Phase 5 covers PRD "5. 생산 라인": status/count display, non-destructive
FIFO listing of the production queue, and production-complete processing
(dequeue front item, PRODUCING -> CONFIRMED, credit stock).
"""

from sampleordersystem.controller.production_controller import ProductionController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.production_queue import ProductionQueue, ProductionQueueItem
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


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
    controller, console, _, _, _ = build_controller(tmp_path, ["1", "4"], queue=queue)

    controller.run_once()

    assert "2" in console.printed_text()


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


def test_complete_production_transitions_order_and_credits_stock(tmp_path):
    queue = ProductionQueue()
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, ["3"], queue=queue)
    sample, order = make_producing_order(sample_repo, order_repo, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0)
    queue.enqueue(
        ProductionQueueItem(
            order_id=order.id, sample_id=sample.id, quantity=10, shortfall=7, actual_production=14, total_time=28.0
        )
    )

    still_running = controller.run_once()

    assert still_running is True
    updated_order = order_repo.find(order.id)
    assert updated_order.status == "CONFIRMED"
    updated_sample = sample_repo.find(sample.id)
    assert updated_sample.stock == 3 + 14
    assert len(queue) == 0
    assert "CONFIRMED" in console.printed_text()


def test_complete_production_on_empty_queue_reports_message_not_crash(tmp_path):
    controller, console, sample_repo, order_repo, queue = build_controller(tmp_path, ["3"])

    still_running = controller.run_once()

    assert still_running is True
    assert "없습니다" in console.printed_text()
    assert order_repo.list_all() == []
    assert sample_repo.list_all() == []


def test_complete_production_dequeues_front_item_only(tmp_path):
    queue = ProductionQueue()
    controller, console, sample_repo, order_repo, _ = build_controller(tmp_path, ["3"], queue=queue)
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

    controller.run_once()

    assert order_repo.find(order_a.id).status == "CONFIRMED"
    assert order_repo.find(order_b.id).status == "PRODUCING"
    assert len(queue) == 1
    remaining = queue.peek()
    assert remaining.order_id == order_b.id


def test_exit_option_stops_the_loop(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["4"])

    still_running = controller.run_once()

    assert still_running is False
    assert "종료" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
