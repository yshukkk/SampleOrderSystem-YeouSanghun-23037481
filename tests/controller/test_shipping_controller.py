"""Integration tests for ShippingController -- driven entirely through fakes.

Phase 6 covers PRD "6. 출고 처리": list CONFIRMED-only orders, and release
a chosen CONFIRMED order to RELEASED via `order_model.release`.

The flow was later redesigned to drop the old numbered menu (1. CONFIRMED
목록 / 2. 출고 처리 / 3. 종료): every call to `run_once()` now auto-shows
the CONFIRMED list first, then directly prompts for an order id -- there
is no separate "list" or "출고 처리" selection step any more. Typing `0`
(the documented back sentinel) returns to the main menu without shipping
anything; any other input is parsed as an order id to ship. After
processing, `run_once()` always returns `True` (unless `0` was fed) so the
caller can loop back here to ship another order without re-entering this
sub-menu.
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


def test_run_once_auto_shows_confirmed_list_without_a_separate_selection(tmp_path):
    # No "1" (or any) list-selection input is fed -- the CONFIRMED list must
    # still appear automatically, before the id prompt.
    sample_repo, order_repo, sample, confirmed_order = make_sample_and_order(
        tmp_path, status="CONFIRMED", customer_name="홍길동"
    )
    reserved_order = order_repo.intake(sample_id=sample.id, customer_name="김철수", quantity=1)

    controller, console, _, _ = build_controller(
        tmp_path, ["0"], order_repository=order_repo, sample_repository=sample_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert str(confirmed_order.id) in printed
    assert "홍길동" in printed
    assert "김철수" not in printed


def test_list_excludes_non_confirmed_orders(tmp_path):
    sample_repo, order_repo, sample, confirmed_order = make_sample_and_order(
        tmp_path, status="CONFIRMED", customer_name="홍길동"
    )
    producing_order = order_repo.intake(sample_id=sample.id, customer_name="박영희", quantity=2)
    order_repo.update_status(producing_order.id, "PRODUCING")
    rejected_order = order_repo.intake(sample_id=sample.id, customer_name="이순신", quantity=3)
    order_repo.update_status(rejected_order.id, "REJECTED")
    released_order = order_repo.intake(sample_id=sample.id, customer_name="강감찬", quantity=4)
    order_repo.update_status(released_order.id, "RELEASED")

    controller, console, _, _ = build_controller(
        tmp_path, ["0"], order_repository=order_repo, sample_repository=sample_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "홍길동" in printed
    assert "박영희" not in printed
    assert "이순신" not in printed
    assert "강감찬" not in printed


def test_list_when_empty_reports_message_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is False
    assert "없습니다" in console.printed_text()


def test_feeding_order_id_directly_ships_it_no_menu_number_needed(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="CONFIRMED")
    controller, console, _, _ = build_controller(
        tmp_path, [str(order.id)], order_repository=order_repo, sample_repository=sample_repo
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
        tmp_path, [str(order.id)], order_repository=order_repo, sample_repository=sample_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated_sample = sample_repo.find(sample.id)
    assert updated_sample.stock == 20 - 7


def test_back_sentinel_zero_returns_to_main_menu_without_shipping(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="CONFIRMED")
    controller, console, _, _ = build_controller(
        tmp_path, ["0"], order_repository=order_repo, sample_repository=sample_repo
    )

    still_running = controller.run_once()

    assert still_running is False
    updated = order_repo.find(order.id)
    assert updated.status == "CONFIRMED"  # unchanged -- nothing shipped
    assert "돌아갑니다" in console.printed_text()


def test_release_reserved_order_fails_gracefully_no_state_change(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="RESERVED")
    controller, console, _, _ = build_controller(
        tmp_path, [str(order.id)], order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "RESERVED"
    assert "허용되지 않은" in console.printed_text()


def test_release_already_released_order_fails_gracefully_no_state_change(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="RELEASED")
    controller, console, _, _ = build_controller(
        tmp_path, [str(order.id)], order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "RELEASED"
    assert "허용되지 않은" in console.printed_text()


def test_release_nonexistent_order_id_reports_error_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["999"])

    still_running = controller.run_once()

    assert still_running is True
    assert "존재하지 않는" in console.printed_text()


def test_release_invalid_number_reports_error_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["abc"])

    still_running = controller.run_once()

    assert still_running is True
    assert "숫자" in console.printed_text()


def test_run_once_returns_true_after_shipping_so_caller_can_loop_for_another(tmp_path):
    # Proves the new flow supports shipping multiple orders in one visit:
    # after a normal ship action, run_once() returns True (not False), so
    # __main__.py's loop calls it again -- re-showing the (now-updated)
    # CONFIRMED list and re-prompting, without the user re-entering this
    # sub-menu from the main menu.
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, status="CONFIRMED")
    controller, console, _, _ = build_controller(
        tmp_path, [str(order.id)], order_repository=order_repo, sample_repository=sample_repo
    )

    still_running = controller.run_once()

    assert still_running is True
