"""Controller for the Sample management console screen.

`SampleController` owns nothing but the wiring: it reads raw strings via an
injected `input_func`, asks the model (`SampleRepository`) to do the work,
and hands the model's result to the view for rendering before pushing it
out through an injected `output_func`. Both hooks default to the real
`input`/`print` builtins so production code needs no extra setup, while
tests can swap in fakes to drive the whole loop without a console.
"""

from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables

INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EXIT_MESSAGE = "시료 관리를 종료합니다."


class SampleController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(self, repository: SampleRepository, input_func=input, output_func=print):
        self._repository = repository
        self._read = input_func
        self._write = output_func
        self._actions = {
            "1": self._register_sample,
            "2": self._list_samples,
            "3": self._search_samples,
        }

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(menus.render_sample_menu())
        choice = self._read().strip()

        if choice == "4":
            self._write(EXIT_MESSAGE)
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True

    def _register_sample(self) -> None:
        name = self._read().strip()
        avg_production_time_raw = self._read().strip()
        yield_rate_raw = self._read().strip()

        avg_production_time = self._parse_float(avg_production_time_raw)
        if avg_production_time is None:
            return
        yield_rate = self._parse_float(yield_rate_raw)
        if yield_rate is None:
            return

        sample = self._repository.register(
            name=name,
            avg_production_time=avg_production_time,
            yield_rate=yield_rate,
        )
        self._write(f"시료가 등록되었습니다: ID={sample.id}")

    def _list_samples(self) -> None:
        samples = self._repository.list_all()
        self._write(tables.render_sample_table(samples))

    def _search_samples(self) -> None:
        query = self._read().strip()
        samples = self._repository.search_by_name(query)
        self._write(tables.render_sample_table(samples))

    def _parse_float(self, raw: str) -> float | None:
        try:
            return float(raw)
        except ValueError:
            self._write(INVALID_NUMBER_MESSAGE.format(raw=raw))
            return None
