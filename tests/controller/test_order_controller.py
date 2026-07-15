"""Integration tests for OrderController -- driven entirely through fakes.

Phase 3 scope only: order intake. Approval/rejection are later phases and
have no controller surface to test yet.
"""

from sampleordersystem.controller.order_controller import OrderController
from sampleordersystem.model.order import OrderRepository
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


def build_controller(tmp_path, answers, sample_repository=None, order_repository=None):
    console = FakeConsole(answers)
    sample_repo = sample_repository or SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = order_repository or OrderRepository(JsonRepository(tmp_path / "orders.json"))
    controller = OrderController(
        order_repo, sample_repo, input_func=console.read, output_func=console.write
    )
    return controller, console, sample_repo, order_repo


def test_intake_is_rejected_for_unregistered_sample_id(tmp_path):
    controller, console, _, order_repo = build_controller(
        tmp_path, ["1", "999", "홍길동", "10"]
    )

    still_running = controller.run_once()

    assert still_running is True
    assert order_repo.list_all() == []
    assert "등록되지 않은" in console.printed_text()


def test_intake_succeeds_and_order_starts_as_reserved(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    sample = sample_repo.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=0.9)
    controller, console, _, order_repo = build_controller(
        tmp_path,
        ["1", str(sample.id), "홍길동", "10"],
        sample_repository=sample_repo,
    )

    still_running = controller.run_once()

    assert still_running is True
    [order] = order_repo.list_all()
    assert order.sample_id == sample.id
    assert order.customer_name == "홍길동"
    assert order.quantity == 10
    assert order.status == "RESERVED"
    assert "RESERVED" in console.printed_text()


def test_intake_with_invalid_sample_id_number_reports_error(tmp_path):
    controller, console, _, order_repo = build_controller(tmp_path, ["1", "abc"])

    still_running = controller.run_once()

    assert still_running is True
    assert "숫자" in console.printed_text()
    assert order_repo.list_all() == []


def test_exit_option_stops_the_loop(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["2"])

    still_running = controller.run_once()

    assert still_running is False
    assert "종료" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
