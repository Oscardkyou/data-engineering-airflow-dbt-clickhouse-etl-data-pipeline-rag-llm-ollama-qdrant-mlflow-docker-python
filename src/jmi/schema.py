"""Unified vacancy schema: every source is normalised into this shape before loading."""

from datetime import date, datetime

import pyarrow as pa
from pydantic import BaseModel, Field, field_validator, model_validator


class Vacancy(BaseModel):
    source: str
    source_id: str
    dt: date                                  # lake partition the record came from
    title: str = Field(min_length=1)
    company: str | None = None
    company_id: str | None = None
    url: str
    published_at: datetime                    # timezone-aware, stored as UTC
    city: str | None = None
    country: str | None = None
    is_remote: bool = False
    location_restrictions: list[str] = []
    employment_type: str | None = None
    seniority: str | None = None
    salary_from: float | None = None
    salary_to: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None          # month | year | hour
    salary_gross: bool | None = None
    skills: list[str] = []
    categories: list[str] = []
    description_html: str = ""

    @field_validator("url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must be http(s)")
        return v

    @field_validator("published_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        return v

    @model_validator(mode="after")
    def _salary_range(self) -> "Vacancy":
        for bound in (self.salary_from, self.salary_to):
            if bound is not None and bound <= 0:
                raise ValueError("salary must be positive")
        if self.salary_from and self.salary_to and self.salary_from > self.salary_to:
            raise ValueError("salary_from > salary_to")
        return self


ARROW_SCHEMA = pa.schema([
    ("source", pa.string()),
    ("source_id", pa.string()),
    ("dt", pa.date32()),
    ("title", pa.string()),
    ("company", pa.string()),
    ("company_id", pa.string()),
    ("url", pa.string()),
    ("published_at", pa.timestamp("ms", tz="UTC")),
    ("city", pa.string()),
    ("country", pa.string()),
    ("is_remote", pa.bool_()),
    ("location_restrictions", pa.list_(pa.string())),
    ("employment_type", pa.string()),
    ("seniority", pa.string()),
    ("salary_from", pa.float64()),
    ("salary_to", pa.float64()),
    ("salary_currency", pa.string()),
    ("salary_period", pa.string()),
    ("salary_gross", pa.bool_()),
    ("skills", pa.list_(pa.string())),
    ("categories", pa.list_(pa.string())),
    ("description_html", pa.string()),
])


def to_arrow(vacancies: list[Vacancy]) -> pa.Table:
    return pa.Table.from_pylist([v.model_dump() for v in vacancies], schema=ARROW_SCHEMA)
