"""Entry point: `python -m sampleordersystem`.

Wires the real `input`/`print` builtins into the sample-management and
order controllers and runs the main menu loop: show a summary + menu,
route to a sub-menu until it signals exit, repeat until the user chooses
to exit the whole application.

Sample management (Phase 2), order intake/approval/rejection + the
production queue (Phase 3/4), the production line's auto-completion
screen (Phase 5), and shipping (Phase 6) exist as sub-menus so far --
monitoring is a later phase and is not routed here yet.
"""

from pathlib import Path

from sampleordersystem.controller.order_controller import OrderController
from sampleordersystem.controller.production_controller import ProductionController
from sampleordersystem.controller.sample_controller import SampleController
from sampleordersystem.controller.shipping_controller import ShippingController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.production_queue import ProductionQueue
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository
from sampleordersystem.view import menus, tables

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SAMPLES_PATH = DATA_DIR / "samples.json"
ORDERS_PATH = DATA_DIR / "orders.json"

EXIT_MESSAGE = "SampleOrderSystem을 종료합니다."
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"


def render_summary(
    sample_repository: SampleRepository,
    order_repository: OrderRepository,
    production_queue_waiting: int,
) -> str:
    samples = sample_repository.list_all()
    orders = order_repository.list_all()
    total_stock = sum(sample.stock for sample in samples)
    return tables.render_summary_line(
        sample_count=len(samples),
        total_stock=total_stock,
        order_count=len(orders),
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
    sample_controller = SampleController(sample_repository)
    order_controller = OrderController(order_repository, sample_repository, production_queue=production_queue)
    production_controller = ProductionController(order_repository, sample_repository, production_queue)
    shipping_controller = ShippingController(order_repository, sample_repository)

    keep_going = True
    while keep_going:
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
            print(EXIT_MESSAGE)
            keep_going = False
        else:
            print(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))


if __name__ == "__main__":
    run()
