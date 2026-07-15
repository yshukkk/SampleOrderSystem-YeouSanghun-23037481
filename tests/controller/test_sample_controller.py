"""Integration tests for SampleController -- driven entirely through fakes.

Each test builds a controller with a canned sequence of "typed" inputs and
a list that captures every "printed" line, so the full menu round-trip is
exercised without touching a real console.
"""

from sampleordersystem.controller.sample_controller import SampleController
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


def build_controller(tmp_path, answers, repository=None):
    console = FakeConsole(answers)
    repo = repository or SampleRepository(JsonRepository(tmp_path / "samples.json"))
    controller = SampleController(repo, input_func=console.read, output_func=console.write)
    return controller, console


def test_register_option_adds_a_new_sample_with_zero_stock(tmp_path):
    controller, console = build_controller(tmp_path, ["1", "1", "시료-A", "2.5", "0.9"])

    still_running = controller.run_once()

    assert still_running is True
    [sample] = controller._repository.list_all()
    assert sample.id == 1
    assert sample.name == "시료-A"
    assert sample.avg_production_time == 2.5
    assert sample.yield_rate == 0.9
    assert sample.stock == 0
    assert "등록" in console.printed_text()
    assert str(sample.id) in console.printed_text()


def test_register_option_with_invalid_number_reports_error(tmp_path):
    controller, console = build_controller(tmp_path, ["1", "1", "시료-A", "abc", "0.9"])

    still_running = controller.run_once()

    assert still_running is True
    assert "숫자" in console.printed_text()
    assert controller._repository.list_all() == []


def test_register_option_with_invalid_id_reports_error(tmp_path):
    controller, console = build_controller(tmp_path, ["1", "abc", "시료-A", "2.5", "0.9"])

    still_running = controller.run_once()

    assert still_running is True
    assert "ID" in console.printed_text()
    assert controller._repository.list_all() == []


def test_register_option_with_duplicate_id_reports_error(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="시료-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(
        tmp_path, ["1", "1", "시료-B", "2.5", "0.9"], repository=repository
    )

    still_running = controller.run_once()

    assert still_running is True
    assert "이미 사용 중인 ID" in console.printed_text()
    samples = repository.list_all()
    assert len(samples) == 1
    assert samples[0].name == "시료-A"


def test_list_option_shows_previously_registered_samples_with_stock(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="시료-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["2"], repository=repository)

    controller.run_once()

    assert "시료-A" in console.printed_text()
    assert "0" in console.printed_text()


def test_search_option_finds_matching_samples_by_name(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    repository.register(id=2, name="Chip-B", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "이름: wafer"], repository=repository)

    controller.run_once()

    assert "Wafer-A" in console.printed_text()
    assert "Chip-B" not in console.printed_text()


def test_search_option_with_no_name_match_shows_empty_message(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "이름: 없음"], repository=repository)

    controller.run_once()

    assert "등록된 시료가 없습니다" in console.printed_text()


def test_search_option_finds_sample_by_id(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    repository.register(id=2, name="Chip-B", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "ID: 1"], repository=repository)

    controller.run_once()

    assert "Wafer-A" in console.printed_text()
    assert "Chip-B" not in console.printed_text()


def test_search_option_with_no_id_match_shows_empty_message(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "ID: 999"], repository=repository)

    controller.run_once()

    assert "등록된 시료가 없습니다" in console.printed_text()


def test_search_option_with_invalid_id_reports_error(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "ID: abc"], repository=repository)

    controller.run_once()

    assert "ID" in console.printed_text()


def test_search_option_with_malformed_format_reports_error(tmp_path):
    repository = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    repository.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    controller, console = build_controller(tmp_path, ["3", "wafer"], repository=repository)

    controller.run_once()

    assert "형식이 올바르지 않습니다" in console.printed_text()


def test_exit_option_stops_the_loop(tmp_path):
    controller, console = build_controller(tmp_path, ["4"])

    still_running = controller.run_once()

    assert still_running is False
    assert "종료" in console.printed_text()


def test_unrecognized_choice_reports_an_error_and_keeps_running(tmp_path):
    controller, console = build_controller(tmp_path, ["0"])

    still_running = controller.run_once()

    assert still_running is True
    assert "잘못된" in console.printed_text()
