"""Controller for the Shipping console screen (PRD "6. 출고 처리").

Redesigned to drop the old numbered menu (1. CONFIRMED 목록 / 2. 출고 처리
/ 3. 종료) entirely: every call to `run_once()` auto-shows the CONFIRMED
order list first, then directly prompts for an order id to ship -- there
is no separate "list" or "출고 처리" selection step, the list-then-prompt
IS the whole interaction. Typing `0` (the documented back sentinel, see
`menus.render_shipping_prompt`) returns to the main menu (`run_once()`
returns `False`) without shipping anything; any other input is parsed as
an order id and an attempt is made to ship it. After processing (success
or a handled error), `run_once()` returns `True` so the caller
(`__main__.py`'s loop) calls it again, re-showing the now-updated
CONFIRMED list and re-prompting -- letting the user ship multiple orders
in one visit without re-navigating the main menu each time.

Ships a chosen order by calling the pure `order_model.release()`
transition (CONFIRMED -> RELEASED), persisting the result via
`OrderRepository.update_status`. No new persistence/table rendering is
needed -- `OrderRepository`/`render_order_table` are reused as-is.

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
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables

BACK_SENTINEL = "0"
EXIT_MESSAGE = "출고 처리에서 돌아갑니다."
INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"
ORDER_NOT_FOUND_MESSAGE = "존재하지 않는 주문 번호입니다: {order_id}"
RELEASE_SUCCESS_MESSAGE = "출고 처리되었습니다: ID={order_id} 상태={status}"
SAMPLE_NOT_FOUND_FOR_ORDER_MESSAGE = "주문에 연결된 시료를 찾을 수 없습니다: {sample_id}"


class ShippingController:
    """Runs one auto-list-then-prompt round-trip per call to `run_once()`."""

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

    def run_once(self) -> bool:
        """Auto-show the CONFIRMED list, prompt for an order id, and report
        whether to continue.

        `0` returns to the main menu without shipping anything (`False`);
        any other input is parsed as an order id and an attempt is made to
        ship it, after which this always returns `True` so the caller loops
        back here (re-showing the updated list) rather than requiring the
        user to re-enter this sub-menu for each order.
        """
        self._write(menus.render_shipping_header())
        self._list_confirmed_orders()
        self._write(menus.render_shipping_prompt())
        raw = self._read().strip()

        if raw == BACK_SENTINEL:
            self._write(EXIT_MESSAGE)
            return False

        self._release_order(raw)
        return True

    def _list_confirmed_orders(self) -> None:
        confirmed = [
            order
            for order in self._order_repository.list_all()
            if order.status == order_model.STATUS_CONFIRMED
        ]
        self._write(tables.render_order_table(confirmed))

    def _release_order(self, raw: str) -> None:
        order_id = self._parse_int(raw)
        if order_id is None:
            return

        order = self._order_repository.find(order_id)
        if order is None:
            self._write(ORDER_NOT_FOUND_MESSAGE.format(order_id=order_id))
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

    def _parse_int(self, raw: str) -> int | None:
        try:
            return int(raw)
        except ValueError:
            self._write(INVALID_NUMBER_MESSAGE.format(raw=raw))
            return None
