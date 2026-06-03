from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class CandidateProfile:
    target_roles: list[str] = field(default_factory=list)
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    remote_ok: bool = True
    levels: list[str] = field(default_factory=list)
    max_age_days: int = 45
    dealbreakers: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Vacancy:
    id: str
    title: str
    company: str
    description: str
    city: str
    remote: bool
    work_format: str
    level: str
    stack: list[str]
    published_at: str
    url: str
    source: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any], source: str) -> "Vacancy":
        stack = raw.get("stack") or raw.get("tags") or raw.get("skills") or ""
        if isinstance(stack, str):
            stack_items = [item.strip() for item in stack.replace(";", ",").split(",") if item.strip()]
        else:
            stack_items = [str(item).strip() for item in stack if str(item).strip()]

        remote_value = raw.get("remote", False)
        if isinstance(remote_value, str):
            remote = remote_value.lower() in {"true", "yes", "1", "remote", "удаленно", "удаленка"}
        else:
            remote = bool(remote_value)

        return cls(
            id=str(raw.get("id") or raw.get("url") or raw.get("slug") or ""),
            title=str(raw.get("title") or raw.get("job_title") or ""),
            company=str(raw.get("company") or raw.get("company_name") or ""),
            description=str(raw.get("description") or raw.get("job_description") or ""),
            city=str(raw.get("city") or raw.get("candidate_required_location") or raw.get("location") or ""),
            remote=remote,
            work_format=str(raw.get("work_format") or ("remote" if remote else "unknown")),
            level=str(raw.get("level") or infer_level(str(raw.get("title", "")), str(raw.get("description", "")))),
            stack=stack_items,
            published_at=str(raw.get("published_at") or raw.get("publication_date") or raw.get("created_at") or ""),
            url=str(raw.get("url") or raw.get("job_url") or ""),
            source=source,
        )

    def text_blob(self) -> str:
        return " ".join(
            [
                self.title,
                self.company,
                self.description,
                self.city,
                self.work_format,
                self.level,
                " ".join(self.stack),
            ]
        ).lower()

    def dedupe_key(self) -> str:
        return "|".join([self.title.strip().lower(), self.company.strip().lower(), self.url.strip().lower()])


@dataclass
class ValidationResult:
    valid: list[Vacancy]
    broken_rows: list[str]
    duplicates: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScoredVacancy:
    vacancy: Vacancy
    score: int
    matched: list[str]
    concerns: list[str]


@dataclass
class VacancyExplanation:
    vacancy_id: str
    why_fit: str
    matched_requirements: list[str]
    concerns: list[str]
    next_step: str
    employer_questions: list[str]


def infer_level(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(word in text for word in ["intern", "internship", "стаж", "стажер", "стажёр"]):
        return "intern"
    if "junior+" in text or "junior plus" in text:
        return "junior+"
    if "junior" in text or "джун" in text:
        return "junior"
    if any(word in text for word in ["senior", "lead", "principal"]):
        return "senior"
    if "middle" in text:
        return "middle"
    return "unknown"


def today_iso() -> str:
    return date.today().isoformat()
