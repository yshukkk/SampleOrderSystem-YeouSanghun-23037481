"""Controller for the Monitoring console screen (PRD "4. 모니터링").

Read-only: this controller never writes to either repository. Both actions
(주문량 확인/재고량 확인) re-read from the injected `OrderRepository`/
`SampleRepository` every time they run -- no caching layer of any kind lives
here, mirroring the "매 조회 시 디스크에서 재로드" principle already
established by `ProductionController`.

주문량 확인: counts orders per status, but only across the four "valid"
statuses PRD calls out (RESERVED/CONFIRMED/PRODUCING/RELEASED). REJECTED is
excluded entirely -- not shown as a zero-count row, not folded into any other
category -- per PRD "REJECTED는 유효한 주문이 아니므로 이 화면에서 제외".

재고량 확인: for each registered sample, classifies its stock level against
"주문 대비" demand, where demand is defined as the sum of quantities across
that sample's currently-active orders -- RESERVED/CONFIRMED/PRODUCING,
mirroring the same "active order" status grouping `__main__.py`'s
`_TERMINAL_ORDER_STATUSES` set already established for the main-menu summary
(RELEASED/REJECTED are terminal and excluded from demand: a RELEASED order's
demand has already been fulfilled and deducted from stock at shipping time,
and a REJECTED order was never fulfilled at all). Classification, in
priority order:
  - stock == 0            -> 고갈 (PRD's literal "재고 수량이 0", checked
                              first regardless of demand -- even a sample
                              with zero active orders still reads as 고갈 if
                              its own stock is 0)
  - stock > 0, stock < demand -> 부족
  - stock > 0, stock >= demand (including demand == 0) -> 여유
"""

from sampleordersystem.model import order as order_model
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables
from sampleordersystem.view.tables import StockStatusRow

UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EXIT_MESSAGE = "모니터링 메뉴에서 돌아갑니다."

# Same "currently active" order-status grouping `__main__.py` uses for the
# main-menu summary's order count (RESERVED/CONFIRMED/PRODUCING) -- reused
# here, unchanged, as the set of orders that count toward a sample's demand.
_ACTIVE_ORDER_STATUSES = {
    order_model.STATUS_RESERVED,
    order_model.STATUS_CONFIRMED,
    order_model.STATUS_PRODUCING,
}


class MonitoringController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(
        self,
        sample_repository: SampleRepository,
        order_repository: OrderRepository,
        input_func=input,
        output_func=print,
    ):
        self._sample_repository = sample_repository
        self._order_repository = order_repository
        self._read = input_func
        self._write = output_func
        self._actions = {
            "1": self._show_order_status_counts,
            "2": self._show_stock_status,
        }

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(menus.render_monitoring_menu())
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

    def _show_order_status_counts(self) -> None:
        orders = self._order_repository.list_all()
        counts: dict[str, int] = {status: 0 for status in tables.ORDER_STATUS_CATEGORIES}
        for order in orders:
            if order.status in counts:
                counts[order.status] += 1
        self._write(tables.render_order_status_counts_table(counts))

    def _show_stock_status(self) -> None:
        samples = self._sample_repository.list_all()
        orders = self._order_repository.list_all()

        demand_by_sample_id: dict[int, int] = {}
        for order in orders:
            if order.status in _ACTIVE_ORDER_STATUSES:
                demand_by_sample_id[order.sample_id] = (
                    demand_by_sample_id.get(order.sample_id, 0) + order.quantity
                )

        rows = [
            StockStatusRow(
                sample=sample,
                status_label=self._classify_stock(sample.stock, demand_by_sample_id.get(sample.id, 0)),
            )
            for sample in samples
        ]
        self._write(tables.render_stock_status_table(rows))

    @staticmethod
    def _classify_stock(stock: int, demand: int) -> str:
        if stock == 0:
            return tables.STOCK_STATUS_DEPLETED
        if stock < demand:
            return tables.STOCK_STATUS_SHORT
        return tables.STOCK_STATUS_SUFFICIENT
