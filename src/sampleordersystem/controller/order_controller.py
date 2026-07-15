"""Controller for the Order console screen: intake + approval/rejection.

Phase 3 scope was intake only. Phase 4 adds the "접수된 주문 목록"
listing and the approve/reject actions from PRD "3. 주문 승인/거절".

The listing was later broadened to show RESERVED **and** PRODUCING orders
(instead of RESERVED-only): a PRODUCING order is otherwise invisible after
a process restart, since `ProductionQueue` is in-memory only and is
rebuilt empty on startup while `orders.json` still correctly says
PRODUCING. Sourcing this listing fresh from `OrderRepository.list_all()`
(re-read from disk every call) rather than from the in-memory queue means
a PRODUCING order stays visible here regardless of whether it also
happens to be sitting in the queue. CONFIRMED/RELEASED/REJECTED orders are
still excluded -- this listing is only for orders that are neither
finished nor yet shippable. The approve/reject actions themselves are
unchanged -- they still only operate on RESERVED orders via
`order_model.approve`/`reject`'s transition guards.

- Approve: RESERVED order + stock >= quantity -> immediate CONFIRMED (no
  production queue entry). RESERVED order + stock < quantity -> PRODUCING,
  with a `ProductionQueueItem` (shortfall/실생산량/총생산시간, per
  `model/production_queue.py`) enqueued onto this controller's
  `ProductionQueue`.
- Reject: RESERVED order -> immediate REJECTED.

Production-line auto-completion (draining the queue), shipping, and
monitoring are later phases and are intentionally not built here -- this
controller only ever *adds* to the production queue, never consumes it.

Follows the same injected `input_func`/`output_func` pattern as
`SampleController` so it can be driven end-to-end in tests without a real
console.
"""

from sampleordersystem.model import order as order_model
from sampleordersystem.model.order import Order, OrderRepository
from sampleordersystem.model.production_queue import (
    ProductionQueue,
    ProductionQueueItem,
    calculate_actual_production,
    calculate_shortfall,
    calculate_total_time,
)
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables

UNKNOWN_SAMPLE_MESSAGE = "등록되지 않은 시료 ID입니다: {sample_id}"
INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EXIT_MESSAGE = "주문 메뉴를 종료합니다."
INTAKE_SUCCESS_MESSAGE = "주문이 접수되었습니다: ID={order_id} 상태={status}"
ORDER_NOT_FOUND_MESSAGE = "존재하지 않는 주문 번호입니다: {order_id}"
SAMPLE_NOT_FOUND_FOR_ORDER_MESSAGE = "주문에 연결된 시료를 찾을 수 없습니다: {sample_id}"
APPROVE_SUCCESS_MESSAGE = "주문이 승인되었습니다: ID={order_id} 상태={status}"
PRODUCTION_QUEUED_MESSAGE = (
    "생산 큐에 등록되었습니다: 부족분={shortfall} 실생산량={actual_production} "
    "총생산시간={total_time}"
)
REJECT_SUCCESS_MESSAGE = "주문이 거절되었습니다: ID={order_id}"


class OrderController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(
        self,
        order_repository: OrderRepository,
        sample_repository: SampleRepository,
        input_func=input,
        output_func=print,
        production_queue: ProductionQueue | None = None,
    ):
        self._order_repository = order_repository
        self._sample_repository = sample_repository
        self._read = input_func
        self._write = output_func
        self.production_queue = production_queue if production_queue is not None else ProductionQueue()
        self._actions = {
            "1": self._intake_order,
            "2": self._list_pending_orders,
            "3": self._approve_order,
            "4": self._reject_order,
        }

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(menus.render_order_menu())
        choice = self._read().strip()

        if choice == "5":
            self._write(EXIT_MESSAGE)
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True

    def _intake_order(self) -> None:
        self._write(menus.render_intake_guide())
        sample_id_raw = self._read().strip()
        sample_id = self._parse_int(sample_id_raw)
        if sample_id is None:
            return

        customer_name = self._read().strip()

        quantity_raw = self._read().strip()
        quantity = self._parse_int(quantity_raw)
        if quantity is None:
            return

        sample = self._sample_repository.find(sample_id)
        if sample is None:
            self._write(UNKNOWN_SAMPLE_MESSAGE.format(sample_id=sample_id))
            return

        order = self._order_repository.intake(
            sample_id=sample_id,
            customer_name=customer_name,
            quantity=quantity,
        )
        self._write(
            INTAKE_SUCCESS_MESSAGE.format(order_id=order.id, status=order.status)
        )

    def _list_pending_orders(self) -> None:
        # RESERVED + PRODUCING only -- read fresh from the repository (not
        # the in-memory production_queue) so a PRODUCING order stays
        # visible here even after a restart wipes the in-memory queue.
        pending = [
            order
            for order in self._order_repository.list_all()
            if order.status in (order_model.STATUS_RESERVED, order_model.STATUS_PRODUCING)
        ]
        self._write(tables.render_order_table(pending))

    def _approve_order(self) -> None:
        self._write(menus.render_approval_guide())
        order = self._read_order_by_id()
        if order is None:
            return

        sample = self._sample_repository.find(order.sample_id)
        if sample is None:
            self._write(SAMPLE_NOT_FOUND_FOR_ORDER_MESSAGE.format(sample_id=order.sample_id))
            return

        try:
            new_status = order_model.approve(order, stock=sample.stock)
        except ValueError as exc:
            self._write(str(exc))
            return

        self._order_repository.update_status(order.id, new_status)

        if new_status == order_model.STATUS_PRODUCING:
            shortfall = calculate_shortfall(order.quantity, sample.stock)
            actual_production = calculate_actual_production(shortfall, sample.yield_rate)
            total_time = calculate_total_time(sample.avg_production_time, actual_production)
            self.production_queue.enqueue(
                ProductionQueueItem(
                    order_id=order.id,
                    sample_id=sample.id,
                    quantity=order.quantity,
                    shortfall=shortfall,
                    actual_production=actual_production,
                    total_time=total_time,
                )
            )
            self._write(
                PRODUCTION_QUEUED_MESSAGE.format(
                    shortfall=shortfall,
                    actual_production=actual_production,
                    total_time=total_time,
                )
            )

        self._write(APPROVE_SUCCESS_MESSAGE.format(order_id=order.id, status=new_status))

    def _reject_order(self) -> None:
        self._write(menus.render_rejection_guide())
        order = self._read_order_by_id()
        if order is None:
            return

        try:
            new_status = order_model.reject(order)
        except ValueError as exc:
            self._write(str(exc))
            return

        self._order_repository.update_status(order.id, new_status)
        self._write(REJECT_SUCCESS_MESSAGE.format(order_id=order.id))

    def _read_order_by_id(self) -> Order | None:
        """Read one line, parse it as an order id, and look up the order.

        Reports (and returns None for) a non-numeric id or an unknown order
        id; otherwise returns the found `Order`.
        """
        order_id = self._parse_int(self._read().strip())
        if order_id is None:
            return None
        order = self._order_repository.find(order_id)
        if order is None:
            self._write(ORDER_NOT_FOUND_MESSAGE.format(order_id=order_id))
            return None
        return order

    def _parse_int(self, raw: str) -> int | None:
        try:
            return int(raw)
        except ValueError:
            self._write(INVALID_NUMBER_MESSAGE.format(raw=raw))
            return None
