"""Entry point: `python -m sampleordersystem`.

Wires the real `input`/`print` builtins into the sample-management and
order-intake controllers and runs the main menu loop: show a summary +
menu, route to a sub-menu until it signals exit, repeat until the user
chooses to exit the whole application.

Only sample management (Phase 2) and order intake (Phase 3) exist as
sub-menus so far -- approval/rejection, production, shipping, and
monitoring are later phases and are not routed here yet.
"""

from pathlib import Path

from sampleordersystem.controller.order_controller import OrderController
from sampleordersystem.controller.sample_controller import SampleController
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository
from sampleordersystem.view import menus, tables

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SAMPLES_PATH = DATA_DIR / "samples.json"
ORDERS_PATH = DATA_DIR / "orders.json"

EXIT_MESSAGE = "SampleOrderSystem을 종료합니다."
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"

# Production queue doesn't exist yet (Phase 4+), so the backlog count is
# honestly reported as 0 rather than inventing data this phase can't have.
PRODUCTION_QUEUE_WAITING_PLACEHOLDER = 0


def render_summary(sample_repository: SampleRepository, order_repository: OrderRepository) -> str:
    samples = sample_repository.list_all()
    orders = order_repository.list_all()
    total_stock = sum(sample.stock for sample in samples)
    return tables.render_summary_line(
        sample_count=len(samples),
        total_stock=total_stock,
        order_count=len(orders),
        production_queue_waiting=PRODUCTION_QUEUE_WAITING_PLACEHOLDER,
    )


def run() -> None:
    sample_repository = SampleRepository(JsonRepository(SAMPLES_PATH))
    order_repository = OrderRepository(JsonRepository(ORDERS_PATH))
    sample_controller = SampleController(sample_repository)
    order_controller = OrderController(order_repository, sample_repository)

    keep_going = True
    while keep_going:
        summary = render_summary(sample_repository, order_repository)
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
            print(EXIT_MESSAGE)
            keep_going = False
        else:
            print(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))


if __name__ == "__main__":
    run()
