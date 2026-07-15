"""Integration tests for MonitoringController -- driven entirely through fakes.

Phase 7 covers PRD "4. 모니터링": read-only status-count and stock-status
views. The most important rules to lock down here: REJECTED orders must
never appear anywhere in the order-count view (not as a zero row, not
folded into another category), and stock status must classify boundary
cases correctly (stock == 0 always reads as 고갈, even with zero demand).
"""

from sampleordersystem.controller.monitoring_controller import MonitoringController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository
from tests.support import FakeConsole


def build_controller(tmp_path, answers, sample_repository=None, order_repository=None):
    console = FakeConsole(answers)
    sample_repo = sample_repository or SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = order_repository or OrderRepository(JsonRepository(tmp_path / "orders.json"))
    controller = MonitoringController(
        sample_repo, order_repo, input_func=console.read, output_func=console.write
    )
    return controller, console, sample_repo, order_repo


def test_order_status_counts_excludes_rejected_entirely(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)

    reserved = order_repo.intake(sample_id=sample.id, customer_name="A", quantity=1)
    confirmed = order_repo.intake(sample_id=sample.id, customer_name="B", quantity=1)
    order_repo.update_status(confirmed.id, "CONFIRMED")
    producing = order_repo.intake(sample_id=sample.id, customer_name="C", quantity=1)
    order_repo.update_status(producing.id, "PRODUCING")
    released = order_repo.intake(sample_id=sample.id, customer_name="D", quantity=1)
    order_repo.update_status(released.id, "RELEASED")
    rejected = order_repo.intake(sample_id=sample.id, customer_name="E", quantity=1)
    order_repo.update_status(rejected.id, "REJECTED")
    # Add a second RESERVED/CONFIRMED/PRODUCING/RELEASED each so counts != 1
    # everywhere and a miscount would be visible.
    order_repo.intake(sample_id=sample.id, customer_name="F", quantity=1)

    controller, console, _, _ = build_controller(
        tmp_path, ["1"], sample_repository=sample_repo, order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    printed = console.printed_text()
    assert "RESERVED | 2" in printed
    assert "CONFIRMED | 1" in printed
    assert "PRODUCING | 1" in printed
    assert "RELEASED | 1" in printed
    assert "REJECTED" not in printed


def test_order_status_counts_when_no_orders_shows_zero_for_all_four(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["1"])

    controller.run_once()

    printed = console.printed_text()
    assert "RESERVED | 0" in printed
    assert "CONFIRMED | 0" in printed
    assert "PRODUCING | 0" in printed
    assert "RELEASED | 0" in printed
    assert "REJECTED" not in printed


def test_stock_status_zero_stock_with_zero_demand_is_depleted(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "고갈" in printed
    assert "여유" not in printed
    assert "부족" not in printed


def test_stock_status_short_when_stock_below_active_demand(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)
    sample_repo._repository.update(sample.id, stock=5)
    order_repo.intake(sample_id=sample.id, customer_name="A", quantity=10)

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "부족" in printed


def test_stock_status_sufficient_when_stock_exactly_equals_demand(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)
    sample_repo._repository.update(sample.id, stock=5)
    order_repo.intake(sample_id=sample.id, customer_name="A", quantity=5)

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "여유" in printed
    assert "부족" not in printed


def test_stock_status_sufficient_when_no_active_orders(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)
    sample_repo._repository.update(sample.id, stock=5)

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "여유" in printed


def test_stock_status_released_and_rejected_orders_do_not_count_as_demand(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(id=1, name="Wafer-1", avg_production_time=1.0, yield_rate=0.9)
    sample_repo._repository.update(sample.id, stock=5)
    released = order_repo.intake(sample_id=sample.id, customer_name="A", quantity=100)
    order_repo.update_status(released.id, "RELEASED")
    rejected = order_repo.intake(sample_id=sample.id, customer_name="B", quantity=100)
    order_repo.update_status(rejected.id, "REJECTED")

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "여유" in printed
    assert "부족" not in printed
    assert "고갈" not in printed


def test_stock_status_when_no_samples_reports_message_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["2"])

    still_running = controller.run_once()

    assert still_running is True
    assert "없습니다" in console.printed_text()


def test_exit_option_stops_the_loop(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["3"])

    still_running = controller.run_once()

    assert still_running is False
    assert "돌아갑니다" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
