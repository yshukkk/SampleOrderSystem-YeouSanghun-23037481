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
INVALID_ID_MESSAGE = "ID는 정수로 입력해야 합니다: {raw}"
DUPLICATE_ID_MESSAGE = "이미 사용 중인 ID입니다: {id}"
INVALID_SEARCH_FORMAT_MESSAGE = (
    "검색 형식이 올바르지 않습니다. 'ID: <숫자>' 또는 '이름: <검색어>' 형식으로 입력하세요."
)
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
        self._write(menus.render_registration_guide())
        id_raw = self._read().strip()
        name = self._read().strip()
        avg_production_time_raw = self._read().strip()
        yield_rate_raw = self._read().strip()

        sample_id = self._parse_int(id_raw)
        if sample_id is None:
            return
        avg_production_time = self._parse_float(avg_production_time_raw)
        if avg_production_time is None:
            return
        yield_rate = self._parse_float(yield_rate_raw)
        if yield_rate is None:
            return

        sample = self._repository.register(
            id=sample_id,
            name=name,
            avg_production_time=avg_production_time,
            yield_rate=yield_rate,
        )
        if sample is None:
            self._write(DUPLICATE_ID_MESSAGE.format(id=sample_id))
            return
        self._write(f"시료가 등록되었습니다: ID={sample.id}")

    def _list_samples(self) -> None:
        samples = self._repository.list_all()
        self._write(tables.render_sample_table(samples))

    def _search_samples(self) -> None:
        self._write(menus.render_search_guide())
        raw = self._read().strip()
        label, sep, value = raw.partition(":")
        if not sep:
            self._write(INVALID_SEARCH_FORMAT_MESSAGE)
            return
        label = label.strip().lower()
        value = value.strip()

        if label == "id":
            sample_id = self._parse_int(value)
            if sample_id is None:
                return
            sample = self._repository.find(sample_id)
            samples = [sample] if sample is not None else []
            self._write(tables.render_sample_table(samples))
        elif label == "이름":
            samples = self._repository.search_by_name(value)
            self._write(tables.render_sample_table(samples))
        else:
            self._write(INVALID_SEARCH_FORMAT_MESSAGE)

    def _parse_float(self, raw: str) -> float | None:
        try:
            return float(raw)
        except ValueError:
            self._write(INVALID_NUMBER_MESSAGE.format(raw=raw))
            return None

    def _parse_int(self, raw: str) -> int | None:
        try:
            return int(raw)
        except ValueError:
            self._write(INVALID_ID_MESSAGE.format(raw=raw))
            return None
