"""Integration tests for ShippingController -- driven entirely through fakes.

Phase 6 covers PRD "6. 출고 처리": list CONFIRMED-only orders, and release
a chosen CONFIRMED order to RELEASED via `order_model.release`.
"""

from sampleordersystem.controller.shipping_controller import ShippingController
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


def build_controller(tmp_path, answers, order_repository=None, sample_repository=None):
    console = FakeConsole(answers)
    order_repo = order_repository or OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample_repo = sample_repository or SampleRepository(JsonRepository(tmp_path / "samples.json"))
    controller = ShippingController(
        order_repo, sample_repo, input_func=console.read, output_func=console.write
    )
    return controller, console, order_repo, sample_repo


def make_sample_and_order(tmp_path, *, status, quantity=5, sample_id=1, customer_name="홍길동"):
    """Build repos with one sample and one order in the given status."""
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=sample_id, name=f"Wafer-{sample_id}", avg_production_time=1.0, yield_rate=0.9)
    order = order_repo.intake(sample_id=sample.id, customer_name=customer_name, quantity=quantity)
    if status != "RESERVED":
        order_repo.update_status(order.id, status)
    order = order_repo.find(order.id)
    return sample_repo, order_repo, sample, order


def test_list_confirmed_orders_excludes_non_confirmed(tmp_path):
    sample_repo, order_repo, sample, confirmed_order = make_sample_and_order(
        tmp_path, status="CONFIRMED", customer_name="홍길동"
    )
    reserved_order = order_repo.intake(sample_id=sample.id, customer_name="김철수", quantity=1)
    producing_order = order_repo.intake(sample_id=sample.id, customer_name="박영희", quantity=2)
    order_repo.update_status(producing_order.id, "PRODUCING")
    rejected_order = order_repo.intake(sample_id=sample.id, customer_name="이순신", quantity=3)
    order_repo.update_status(rejected_order.id, "REJECTED")
    released_order = order_repo.intake(sample_id=sample.id, customer_name="강감찬", quantity=4)
    order_repo.update_status(released_order.id, "RELEASED")

    controller, console, _, _ = build_controller(
        tmp_path, ["1"], order_repository=order_repo, sample_repository=sample_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert str(confirmed_order.id) in printed
    assert "홍길동" in printed
    assert "김철수" not in printed
    assert "박영희" not in printed
    assert "이순신" not in printed
    assert "강감찬" not in printed


def test_list_confirmed_orders_when_empty_reports_message_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["1"])

    still_running = controller.run_once()

    assert still_running is True
    assert "없습니다" in console.printed_text()


def test_release_confirmed_order_transitions_to_released(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="CONFIRMED")
    controller, console, _, _ = build_controller(
        tmp_path, ["2", str(order.id)], order_repository=order_repo, sample_repository=sample_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "RELEASED"
    assert "RELEASED" in console.printed_text()


def test_release_deducts_shipped_quantity_from_sample_stock(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(
        tmp_path, status="CONFIRMED", quantity=7
    )
    sample_repo._repository.update(sample.id, stock=20)
    controller, console, _, _ = build_controller(
        tmp_path, ["2", str(order.id)], order_repository=order_repo, sample_repository=sample_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated_sample = sample_repo.find(sample.id)
    assert updated_sample.stock == 20 - 7


def test_release_reserved_order_fails_gracefully_no_state_change(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="RESERVED")
    controller, console, _, _ = build_controller(
        tmp_path, ["2", str(order.id)], order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "RESERVED"
    assert "허용되지 않은" in console.printed_text()


def test_release_already_released_order_fails_gracefully_no_state_change(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="RELEASED")
    controller, console, _, _ = build_controller(
        tmp_path, ["2", str(order.id)], order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "RELEASED"
    assert "허용되지 않은" in console.printed_text()


def test_release_nonexistent_order_id_reports_error_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["2", "999"])

    still_running = controller.run_once()

    assert still_running is True
    assert "존재하지 않는" in console.printed_text()


def test_release_invalid_number_reports_error_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["2", "abc"])

    still_running = controller.run_once()

    assert still_running is True
    assert "숫자" in console.printed_text()


def test_exit_option_stops_the_loop(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["3"])

    still_running = controller.run_once()

    assert still_running is False
    assert "종료" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
