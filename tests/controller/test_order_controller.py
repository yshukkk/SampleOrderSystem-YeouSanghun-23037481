"""Integration tests for OrderController -- driven entirely through fakes.

Phase 3 covered order intake. Phase 4 adds the "접수된 주문 목록" listing
and the approve/reject actions (PRD "3. 주문 승인/거절") plus the
production queue they feed on the insufficient-stock branch. The listing
was briefly broadened to RESERVED+PRODUCING (to work around PRODUCING
orders being invisible after a restart) and has since reverted to
RESERVED-only now that `production_started_at` persistence lets
`rebuild_production_queue` reconstruct the queue reliably -- PRODUCING
orders are visible via the "생산 라인" screen instead (see
`test_list_reserved_orders_excludes_producing_and_others`).
"""

from sampleordersystem.controller.order_controller import OrderController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository
from tests.support import FakeConsole


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
    assert "주문 접수 입력 순서" in console.printed_text()


def test_intake_with_invalid_sample_id_number_reports_error(tmp_path):
    controller, console, _, order_repo = build_controller(tmp_path, ["1", "abc"])

    still_running = controller.run_once()

    assert still_running is True
    assert "숫자" in console.printed_text()
    assert order_repo.list_all() == []


def test_exit_option_stops_the_loop(tmp_path):
    # Phase 4 added approve/reject/list options, pushing exit from "2" to "5".
    controller, console, _, _ = build_controller(tmp_path, ["5"])

    still_running = controller.run_once()

    assert still_running is False
    assert "돌아갑니다" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()


def test_bare_order_menu_display_does_not_show_intake_guide(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["5"])

    controller.run_once()

    assert "주문 접수 입력 순서" not in console.printed_text()


def make_sample_and_order(tmp_path, *, stock, quantity, yield_rate=0.5, avg_production_time=2.0):
    """Build repos with one sample (given stock) and one RESERVED order for it."""
    sample_json_repo = JsonRepository(tmp_path / "samples.json")
    sample_repo = SampleRepository(sample_json_repo)
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    sample = sample_repo.register(
        id=1, name="Wafer-A", avg_production_time=avg_production_time, yield_rate=yield_rate
    )
    # Directly bump stock past the always-0 initial value -- there is no
    # public "adjust stock" API yet (that belongs to Phase 5's production
    # completion / Phase 6's shipping), so tests reach into the underlying
    # JsonRepository the same way a future phase's stock-crediting code
    # would call `update(id, stock=...)`.
    sample_json_repo.update(sample.id, stock=stock)
    sample = sample_repo.find(sample.id)
    order = order_repo.intake(sample_id=sample.id, customer_name="홍길동", quantity=quantity)
    return sample_repo, order_repo, sample, order


def test_list_reserved_orders_excludes_producing_and_others(tmp_path):
    sample_repo, order_repo, sample, reserved_order = make_sample_and_order(
        tmp_path, stock=100, quantity=5
    )
    producing_order = order_repo.intake(sample_id=sample.id, customer_name="박영희", quantity=2)
    order_repo.update_status(producing_order.id, "PRODUCING")
    confirmed_order = order_repo.intake(sample_id=sample.id, customer_name="김철수", quantity=1)
    order_repo.update_status(confirmed_order.id, "CONFIRMED")
    released_order = order_repo.intake(sample_id=sample.id, customer_name="이민수", quantity=1)
    order_repo.update_status(released_order.id, "CONFIRMED")
    order_repo.update_status(released_order.id, "RELEASED")
    rejected_order = order_repo.intake(sample_id=sample.id, customer_name="최지우", quantity=1)
    order_repo.update_status(rejected_order.id, "REJECTED")

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    printed = console.printed_text()
    assert "홍길동" in printed
    assert "박영희" not in printed
    assert "김철수" not in printed
    assert "이민수" not in printed
    assert "최지우" not in printed


def test_list_reserved_orders_excludes_producing_even_with_empty_queue(tmp_path):
    # A PRODUCING order (e.g. restored after a restart, with the in-memory
    # ProductionQueue freshly built and empty) must still be excluded from
    # this RESERVED-only listing -- it belongs on the "생산 라인" screen's
    # own listing instead, never here, regardless of the in-memory queue's
    # state. `make_sample_and_order` also creates one genuinely RESERVED
    # order, which must still show up so this isn't just an empty-list case.
    sample_repo, order_repo, sample, reserved_order = make_sample_and_order(
        tmp_path, stock=0, quantity=5
    )
    producing_order = order_repo.intake(sample_id=sample.id, customer_name="복원됨", quantity=3)
    order_repo.update_status(producing_order.id, "PRODUCING")

    controller, console, _, _ = build_controller(
        tmp_path, ["2"], sample_repository=sample_repo, order_repository=order_repo
    )
    assert len(controller.production_queue) == 0

    controller.run_once()

    printed = console.printed_text()
    assert "홍길동" in printed  # the RESERVED order is still shown
    # Note: don't assert the raw order id string is absent -- it can
    # coincidentally match unrelated digits in the menu text itself. The
    # customer name is an unambiguous stand-in.
    assert "복원됨" not in printed


def test_approve_with_sufficient_stock_confirms_immediately_no_queue_entry(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, stock=10, quantity=5)
    controller, console, _, _ = build_controller(
        tmp_path, ["3", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    updated = order_repo.find(order.id)
    assert updated.status == "CONFIRMED"
    assert len(controller.production_queue) == 0
    assert "CONFIRMED" in console.printed_text()


def test_approve_with_stock_exactly_equal_to_quantity_confirms_immediately(tmp_path):
    # Boundary: stock == quantity must go to CONFIRMED, not PRODUCING.
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, stock=5, quantity=5)
    controller, _, _, _ = build_controller(
        tmp_path, ["3", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    updated = order_repo.find(order.id)
    assert updated.status == "CONFIRMED"
    assert len(controller.production_queue) == 0


def test_approve_with_insufficient_stock_producing_and_enqueues_correct_numbers(tmp_path):
    # quantity=10, stock=3 -> shortfall=7; yield_rate=0.5 -> ceil(7/0.5)=14;
    # avg_production_time=2.0 -> total_time=28.0
    sample_repo, order_repo, sample, order = make_sample_and_order(
        tmp_path, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0
    )
    controller, console, _, _ = build_controller(
        tmp_path, ["3", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    updated = order_repo.find(order.id)
    assert updated.status == "PRODUCING"
    assert len(controller.production_queue) == 1
    queued = controller.production_queue.peek()
    assert queued.order_id == order.id
    assert queued.sample_id == sample.id
    assert queued.quantity == 10
    assert queued.shortfall == 7
    assert queued.actual_production == 14
    assert queued.total_time == 28.0
    assert "PRODUCING" in console.printed_text()


def test_approve_with_insufficient_stock_persists_production_started_at(tmp_path):
    # Fix 1: when an approved order becomes the front of the (empty)
    # production line immediately, its real wall-clock `started_at` must be
    # persisted onto the order record (not just held in the in-memory queue
    # item) so it survives a restart -- see `rebuild_production_queue`.
    sample_repo, order_repo, sample, order = make_sample_and_order(
        tmp_path, stock=3, quantity=10, yield_rate=0.5, avg_production_time=2.0
    )
    controller, console, _, _ = build_controller(
        tmp_path, ["3", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    queued = controller.production_queue.peek()
    assert queued.started_at is not None

    record = order_repo.find_raw(order.id)
    assert record["production_started_at"] == queued.started_at


def test_reject_transitions_reserved_order_to_rejected(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, stock=0, quantity=1)
    controller, console, _, _ = build_controller(
        tmp_path, ["4", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    controller.run_once()

    updated = order_repo.find(order.id)
    assert updated.status == "REJECTED"
    assert "거절" in console.printed_text()


def test_approve_already_confirmed_order_reports_error_not_crash(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, stock=10, quantity=5)
    order_repo.update_status(order.id, "CONFIRMED")

    controller, console, _, _ = build_controller(
        tmp_path, ["3", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "CONFIRMED"
    assert "허용되지 않은" in console.printed_text()


def test_reject_already_confirmed_order_reports_error_not_crash(tmp_path):
    sample_repo, order_repo, sample, order = make_sample_and_order(tmp_path, stock=10, quantity=5)
    order_repo.update_status(order.id, "CONFIRMED")

    controller, console, _, _ = build_controller(
        tmp_path, ["4", str(order.id)], sample_repository=sample_repo, order_repository=order_repo
    )

    still_running = controller.run_once()

    assert still_running is True
    updated = order_repo.find(order.id)
    assert updated.status == "CONFIRMED"
    assert "허용되지 않은" in console.printed_text()


def test_approve_unknown_order_id_reports_error_not_crash(tmp_path):
    controller, console, _, _ = build_controller(tmp_path, ["3", "999"])

    still_running = controller.run_once()

    assert still_running is True
    assert "존재하지 않는" in console.printed_text()
