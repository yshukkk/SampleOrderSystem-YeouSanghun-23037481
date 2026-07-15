"""Entry point: `python -m sampleordersystem`.

Wires the real `input`/`print` builtins into the sample-management and
order controllers and runs the main menu loop: show a summary + menu,
route to a sub-menu until it signals exit, repeat until the user chooses
to exit the whole application.

Sample management (Phase 2), order intake/approval/rejection + the
production queue (Phase 3/4), the production line's auto-completion
screen (Phase 5), shipping (Phase 6), and monitoring (Phase 7) all exist
as sub-menus.
"""

from pathlib import Path

from sampleordersystem.controller.monitoring_controller import MonitoringController
from sampleordersystem.controller.order_controller import OrderController
from sampleordersystem.controller.production_controller import ProductionController
from sampleordersystem.controller.sample_controller import SampleController
from sampleordersystem.controller.shipping_controller import ShippingController
from sampleordersystem.model import order as order_model
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.production_queue import ProductionQueue, rebuild_production_queue
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository
from sampleordersystem.view import menus, tables

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SAMPLES_PATH = DATA_DIR / "samples.json"
ORDERS_PATH = DATA_DIR / "orders.json"

EXIT_MESSAGE = "SampleOrderSystem을 종료합니다."
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"


_TERMINAL_ORDER_STATUSES = {order_model.STATUS_RELEASED, order_model.STATUS_REJECTED}


def render_summary(
    sample_repository: SampleRepository,
    order_repository: OrderRepository,
    production_queue_waiting: int,
) -> str:
    samples = sample_repository.list_all()
    orders = order_repository.list_all()
    active_order_count = sum(1 for order in orders if order.status not in _TERMINAL_ORDER_STATUSES)
    return tables.render_summary_line(
        sample_count=len(samples),
        order_count=active_order_count,
        production_queue_waiting=production_queue_waiting,
    )


def run() -> None:
    sample_repository = SampleRepository(JsonRepository(SAMPLES_PATH))
    order_repository = OrderRepository(JsonRepository(ORDERS_PATH))
    # One shared queue instance: OrderController's approval branch enqueues
    # onto it, ProductionController drains it -- both must reference the
    # same object so approving an order in one sub-menu is immediately
    # visible in the other within this process run (the queue itself is
    # in-memory only, not persisted to JSON).
    production_queue = ProductionQueue()
    # Best-effort restore: any order left PRODUCING by a previous process run
    # is otherwise stuck forever (orders.json still says PRODUCING, but the
    # in-memory queue that could complete it is gone). Recomputes
    # shortfall/실생산량/총생산시간 from the sample's *current* stock and
    # restarts that item's production timer from zero -- see
    # `rebuild_production_queue`'s docstring for the full set of accepted
    # limitations of this reconstruction.
    rebuild_production_queue(order_repository, sample_repository, production_queue)
    sample_controller = SampleController(sample_repository)
    order_controller = OrderController(order_repository, sample_repository, production_queue=production_queue)
    production_controller = ProductionController(order_repository, sample_repository, production_queue)
    shipping_controller = ShippingController(order_repository, sample_repository)
    monitoring_controller = MonitoringController(sample_repository, order_repository)

    keep_going = True
    while keep_going:
        # Second auto-drain poll point (the first is at the top of
        # `ProductionController.run_once()`): this app is synchronous and
        # single-threaded with no background thread/timer, so a ready
        # production item can only actually complete at a point the code
        # regains control. Draining here too means completion happens as
        # soon as control returns to the main menu, even if the user was
        # bouncing between 시료/주문/출고/모니터링 sub-menus and never
        # entered 생산 라인 at all.
        for message in production_controller.drain_ready_items():
            print(message)

        summary = render_summary(
            sample_repository, order_repository, len(production_queue)
        )
        print(menus.render_main_menu(summary))
        choice = input().strip()

        if choice == "1":
            sub_running = True
            while sub_running:
                sub_running = sample_controller.run_once()
        elif choice == "2":
            sub_running = True
            while sub_running:
                sub_running = order_controller.run_once()
        elif choice == "3":
            sub_running = True
            while sub_running:
                sub_running = production_controller.run_once()
        elif choice == "4":
            sub_running = True
            while sub_running:
                sub_running = shipping_controller.run_once()
        elif choice == "5":
            sub_running = True
            while sub_running:
                sub_running = monitoring_controller.run_once()
        elif choice == "6":
            print(EXIT_MESSAGE)
            keep_going = False
        else:
            print(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))


if __name__ == "__main__":
    run()
