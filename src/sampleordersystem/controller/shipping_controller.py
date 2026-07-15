"""Controller for the Shipping console screen (PRD "6. 출고 처리").

Mirrors the "select -> look up -> transition -> persist -> report" flow
already established by `OrderController`'s approve/reject actions: list
CONFIRMED-only orders, and ship a chosen order by calling the pure
`order_model.release()` transition (CONFIRMED -> RELEASED), persisting the
result via `OrderRepository.update_status`. No new persistence/table
rendering is needed -- `OrderRepository`/`render_order_table` are reused
as-is (per PLAN.md Phase 6).

Stock (Sample's "즉시 출고 가능한 수량" per PRD.md) is deducted on a
successful release: goods only actually leave via shipping, so that's the
point stock should decrease, by exactly the shipped order's quantity (via
`SampleRepository.remove_stock`). If the order's linked sample can't be
found (a data-consistency edge case, not expected in normal operation), we
report it clearly but still let the RELEASED transition stand -- the order
status change is the primary requirement here, mirroring how
`order_controller.py`'s approve flow reports (rather than blocks on) a
missing linked sample.

Follows the same injected `input_func`/`output_func` pattern as
`SampleController`/`OrderController`/`ProductionController` so it can be
driven end-to-end in tests without a real console.
"""

from sampleordersystem.model import order as order_model
from sampleordersystem.model.order import Order, OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables

UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EXIT_MESSAGE = "출고 처리 메뉴를 종료합니다."
INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"
ORDER_NOT_FOUND_MESSAGE = "존재하지 않는 주문 번호입니다: {order_id}"
RELEASE_SUCCESS_MESSAGE = "출고 처리되었습니다: ID={order_id} 상태={status}"
SAMPLE_NOT_FOUND_FOR_ORDER_MESSAGE = "주문에 연결된 시료를 찾을 수 없습니다: {sample_id}"


class ShippingController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(
        self,
        order_repository: OrderRepository,
        sample_repository: SampleRepository,
        input_func=input,
        output_func=print,
    ):
        self._order_repository = order_repository
        self._sample_repository = sample_repository
        self._read = input_func
        self._write = output_func
        self._actions = {
            "1": self._list_confirmed_orders,
            "2": self._release_order,
        }

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(menus.render_shipping_menu())
        choice = self._read().strip()

        if choice == "3":
            self._write(EXIT_MESSAGE)
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True

    def _list_confirmed_orders(self) -> None:
        confirmed = [
            order
            for order in self._order_repository.list_all()
            if order.status == order_model.STATUS_CONFIRMED
        ]
        self._write(tables.render_order_table(confirmed))

    def _release_order(self) -> None:
        self._write(menus.render_shipping_guide())
        order = self._read_order_by_id()
        if order is None:
            return

        try:
            new_status = order_model.release(order)
        except ValueError as exc:
            self._write(str(exc))
            return

        self._order_repository.update_status(order.id, new_status)

        updated_sample = self._sample_repository.remove_stock(order.sample_id, order.quantity)
        if updated_sample is None:
            self._write(SAMPLE_NOT_FOUND_FOR_ORDER_MESSAGE.format(sample_id=order.sample_id))

        self._write(RELEASE_SUCCESS_MESSAGE.format(order_id=order.id, status=new_status))

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
