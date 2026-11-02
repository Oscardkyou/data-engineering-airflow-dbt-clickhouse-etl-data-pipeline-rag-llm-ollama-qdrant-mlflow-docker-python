"""Data quality gate between the raw lake and the warehouse.

Soft issues (a few invalid rows, duplicates) are fixed and counted; hard issues fail the
load so bad data never reaches ClickHouse. Every outcome is written to raw.load_audit.
"""

import logging
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

from pydantic import ValidationError

from jmi.schema import Vacancy

log = logging.getLogger(__name__)

MAX_INVALID_SHARE = 0.10   # more than 10% unparseable rows = the source changed its format
MIN_ROWS_VS_MEDIAN = 0.5   # fewer than half the usual volume = broken ingest or API outage
MIN_HISTORY_DAYS = 3       # no anomaly check until there is enough history


class DataQualityError(Exception):
    pass


@dataclass
class QualityReport:
    rows_raw: int = 0
    rows_valid: int = 0
    invalid: int = 0
    duplicates: int = 0
    median_rows: float | None = None
    errors: list[str] = field(default_factory=list)   # hard failures
    samples: list[str] = field(default_factory=list)  # first few validation messages

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return asdict(self) | {"ok": self.ok}


def validate(records: Iterable[dict], history: list[int]) -> tuple[list[Vacancy], QualityReport]:
    """Validate, dedupe and check volume. `history` = loaded row counts of previous days."""
    report = QualityReport()
    by_id: dict[str, Vacancy] = {}
    for record in records:
        report.rows_raw += 1
        try:
            vacancy = Vacancy.model_validate(record)
        except ValidationError as exc:
            report.invalid += 1
            if len(report.samples) < 5:
                report.samples.append(f"{record.get('source_id')}: {exc.errors()[0]['msg']}")
            continue
        if vacancy.source_id in by_id:
            report.duplicates += 1  # same job matched several search queries
        by_id[vacancy.source_id] = vacancy

    vacancies = list(by_id.values())
    report.rows_valid = len(vacancies)

    if report.rows_raw == 0:
        report.errors.append("empty batch: source returned no records")
    elif report.invalid / report.rows_raw > MAX_INVALID_SHARE:
        report.errors.append(f"{report.invalid}/{report.rows_raw} rows failed validation")

    if len(history) >= MIN_HISTORY_DAYS:
        report.median_rows = statistics.median(history)
        if report.rows_valid < MIN_ROWS_VS_MEDIAN * report.median_rows:
            report.errors.append(f"volume anomaly: {report.rows_valid} rows vs median {report.median_rows:g}")

    log.info("quality: %s", report.as_dict())
    return vacancies, report
