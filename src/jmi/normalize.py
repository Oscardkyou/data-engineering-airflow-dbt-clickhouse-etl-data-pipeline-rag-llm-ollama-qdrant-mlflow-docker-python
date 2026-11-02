"""Raw API payloads -> unified Vacancy records, one normaliser per source.

Normalisers are pure functions (dict in, dict out) so they are trivial to unit-test;
validation and quality accounting happen in jmi.quality.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime

from jmi.skills import canonical_skill, extract_skills, html_to_text

HH_PERIOD = "month"  # hh salaries are always monthly
HIMALAYAS_PERIOD = {"annual": "year", "monthly": "month", "hourly": "hour"}


def _positive(value) -> float | None:
    return float(value) if value else None  # 0 / None mean "not specified"


def normalize_hh(payload: dict, dt: date) -> dict:
    salary = payload.get("salary") or {}
    text = html_to_text(payload.get("description", ""))
    key_skills = [canonical_skill(s["name"]) for s in payload.get("key_skills") or []]
    return {
        "source": "hh",
        "source_id": str(payload["id"]),
        "dt": dt,
        "title": payload.get("name", ""),
        "company": (payload.get("employer") or {}).get("name"),
        "company_id": (payload.get("employer") or {}).get("id"),
        "url": payload.get("alternate_url", ""),
        "published_at": datetime.fromisoformat(payload["published_at"]),
        "city": (payload.get("area") or {}).get("name"),
        "country": "Kazakhstan",
        "is_remote": (payload.get("schedule") or {}).get("id") == "remote",
        "employment_type": (payload.get("employment") or {}).get("name"),
        "seniority": (payload.get("experience") or {}).get("name"),
        "salary_from": _positive(salary.get("from")),
        "salary_to": _positive(salary.get("to")),
        "salary_currency": salary.get("currency"),
        "salary_period": HH_PERIOD if salary else None,
        "salary_gross": salary.get("gross"),
        "skills": sorted(set(key_skills) | set(extract_skills(payload.get("name", ""), text))),
        "categories": [r["name"] for r in payload.get("professional_roles") or []],
        "description_html": payload.get("description", ""),
    }


def himalayas_id(guid: str) -> str:
    """'https://himalayas.app/companies/acme/jobs/data-engineer' -> 'acme/data-engineer'.

    The job slug alone is not unique: many companies post a "senior-data-engineer".
    """
    parts = guid.rstrip("/").split("/")
    return f"{parts[-3]}/{parts[-1]}" if len(parts) >= 3 and parts[-2] == "jobs" else guid


def normalize_himalayas(job: dict, dt: date) -> dict:
    text = html_to_text(job.get("description", ""))
    seniority = job.get("seniority") or []
    has_salary = bool(job.get("minSalary") or job.get("maxSalary"))
    return {
        "source": "himalayas",
        "source_id": himalayas_id(job["guid"]),
        "dt": dt,
        "title": job.get("title", ""),
        "company": job.get("companyName"),
        "company_id": job.get("companySlug"),
        "url": job.get("applicationLink") or job["guid"],
        "published_at": datetime.fromtimestamp(job["pubDate"], tz=UTC),
        "city": "remote",
        "country": None,
        "is_remote": True,
        "location_restrictions": job.get("locationRestrictions") or [],
        "employment_type": job.get("employmentType"),
        "seniority": ", ".join(seniority) or None,
        "salary_from": _positive(job.get("minSalary")),
        "salary_to": _positive(job.get("maxSalary")),
        "salary_currency": job.get("currency") if has_salary else None,
        "salary_period": HIMALAYAS_PERIOD.get(job.get("salaryPeriod")) if has_salary else None,
        "skills": extract_skills(job.get("title", ""), text),
        "categories": job.get("categories") or [],
        "description_html": job.get("description", ""),
    }


def iter_records(source: str, pages: dict[str, object], dt: date) -> Iterator[dict]:
    """Yield normalised dicts from one raw partition ({key: payload})."""
    if source == "hh":
        # Detail pages are a superset of search results, so search pages are skipped.
        for key, payload in pages.items():
            if key.startswith("vacancy/"):
                yield normalize_hh(payload, dt)
    elif source == "himalayas":
        for payload in pages.values():
            for job in payload.get("jobs", []):
                yield normalize_himalayas(job, dt)
    else:
        raise ValueError(f"no normaliser for source {source}")
