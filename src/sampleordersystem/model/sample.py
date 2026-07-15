"""Sample entity and its JSON-file-backed CRUD repository.

`Sample` mirrors the domain model in PRD.md (id/name/avg_production_time/
yield_rate/stock). `SampleRepository` wraps a `JsonRepository` instance
(persistence-agnostic dict CRUD) and adds the domain-specific convenience
methods a console controller needs: registering a new sample (stock always
starts at 0, per PRD), listing, finding by id, and searching by name.

No console I/O lives here -- persistence is delegated to the injected
`JsonRepository`, and rendering is the view layer's job.
"""

from __future__ import annotations

from dataclasses import dataclass

from sampleordersystem.persistence import JsonRepository

INITIAL_STOCK = 0


@dataclass
class Sample:
    id: int
    name: str
    avg_production_time: float
    yield_rate: float
    stock: int = INITIAL_STOCK

    @classmethod
    def from_record(cls, record: dict) -> "Sample":
        return cls(
            id=record["id"],
            name=record["name"],
            avg_production_time=record["avg_production_time"],
            yield_rate=record["yield_rate"],
            stock=record["stock"],
        )


class SampleRepository:
    """Domain-convenience wrapper around a `JsonRepository` of samples."""

    def __init__(self, repository: JsonRepository) -> None:
        self._repository = repository

    def register(
        self, id: int, name: str, avg_production_time: float, yield_rate: float
    ) -> Sample | None:
        """Register a new sample under a caller-supplied id (the primary key).

        Stock always starts at 0 (PRD hard requirement). Returns `None` if
        `id` is already in use (caller decides how to report the duplicate).
        """
        record = self._repository.create_with_id(
            {
                "name": name,
                "avg_production_time": avg_production_time,
                "yield_rate": yield_rate,
                "stock": INITIAL_STOCK,
            },
            id,
        )
        if record is None:
            return None
        return Sample.from_record(record)

    def list_all(self) -> list[Sample]:
        return [Sample.from_record(record) for record in self._repository.list_all()]

    def find(self, sample_id: int) -> Sample | None:
        record = self._repository.find(sample_id)
        if record is None:
            return None
        return Sample.from_record(record)

    def search_by_name(self, query: str) -> list[Sample]:
        """Return every sample whose name contains `query` (case-insensitive)."""
        needle = query.lower()
        return [sample for sample in self.list_all() if needle in sample.name.lower()]
