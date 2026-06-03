from __future__ import annotations

from datetime import date, datetime
from difflib import SequenceMatcher

from .models import CandidateProfile, ScoredVacancy, Vacancy, ValidationResult


REQUIRED_FIELDS = ["title", "company", "description", "url"]


def split_values(value: str) -> list[str]:
    clean = value.replace("\n", ",").replace(";", ",")
    return [item.strip() for item in clean.split(",") if item.strip()]


def parse_bool(value: str, default: bool = True) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"true", "yes", "1", "да", "remote", "удаленно", "удалённо"}


def parse_criteria(text: str, resume: str = "") -> CandidateProfile:
    data: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()

    combined = f"{resume}\n{text}".lower()
    inferred_skills = []
    for skill in ["Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "Git", "REST API", "LLM", "Telegram Bot", "aiogram", "asyncio"]:
        if skill.lower() in combined:
            inferred_skills.append(skill)

    return CandidateProfile(
        target_roles=split_values(data.get("target_roles", "")) or ["Python Developer", "Backend Developer", "LLM Engineer"],
        must_have_skills=split_values(data.get("must_have_skills", "")) or inferred_skills[:5],
        nice_to_have_skills=split_values(data.get("nice_to_have_skills", "")) or inferred_skills[5:],
        preferred_locations=split_values(data.get("preferred_locations", "")) or ["remote", "Москва", "Санкт-Петербург"],
        remote_ok=parse_bool(data.get("remote_ok", "true")),
        levels=split_values(data.get("level", "")) or ["intern", "junior", "junior+"],
        max_age_days=int(data.get("max_age_days", "45") or 45),
        dealbreakers=split_values(data.get("dealbreakers", "")) or ["senior", "lead", "unpaid", "3+ years"],
        summary=resume[:700].strip(),
    )


def validate_vacancies(vacancies: list[Vacancy]) -> ValidationResult:
    if not vacancies:
        return ValidationResult(valid=[], broken_rows=["Источник не вернул вакансии."], duplicates=0)

    valid: list[Vacancy] = []
    broken: list[str] = []
    seen: set[str] = set()
    duplicates = 0

    for index, vacancy in enumerate(vacancies, start=1):
        missing = [field for field in REQUIRED_FIELDS if not getattr(vacancy, field)]
        if missing:
            broken.append(f"Строка {index}: пропущены поля {', '.join(missing)}")
            continue
        key = vacancy.dedupe_key()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        valid.append(vacancy)

    warnings = []
    if len(valid) < 10:
        warnings.append(f"После валидации осталось {len(valid)} вакансий, меньше целевых 10.")
    return ValidationResult(valid=valid, broken_rows=broken, duplicates=duplicates, warnings=warnings)


def score_vacancies(vacancies: list[Vacancy], profile: CandidateProfile) -> list[ScoredVacancy]:
    scored = [score_one(vacancy, profile) for vacancy in vacancies]
    return sorted(scored, key=lambda item: item.score, reverse=True)


def score_one(vacancy: Vacancy, profile: CandidateProfile) -> ScoredVacancy:
    blob = vacancy.text_blob()
    title = vacancy.title.lower()
    score = 0
    matched: list[str] = []
    concerns: list[str] = []

    role_score = best_role_score(title, profile.target_roles)
    if role_score >= 0.45:
        points = int(20 * role_score)
        score += points
        matched.append(f"роль похожа на целевую (+{points})")
    else:
        concerns.append("роль слабо совпадает с целевой")

    must_matches = matched_terms(blob, profile.must_have_skills)
    nice_matches = matched_terms(blob, profile.nice_to_have_skills)
    score += min(30, len(must_matches) * 6)
    score += min(14, len(nice_matches) * 3)
    if must_matches:
        matched.append("must-have навыки: " + ", ".join(must_matches))
    else:
        concerns.append("не видно must-have навыков")
    if nice_matches:
        matched.append("nice-to-have навыки: " + ", ".join(nice_matches))

    if level_matches(vacancy.level, blob, profile.levels):
        score += 15
        matched.append(f"уровень подходит: {vacancy.level}")
    else:
        score -= 8
        concerns.append(f"уровень может не подойти: {vacancy.level or 'не указан'}")

    if location_matches(vacancy, profile):
        score += 15
        matched.append("формат/локация подходят")
    else:
        score -= 10
        concerns.append("формат работы или локация хуже предпочтений")

    recency = recency_points(vacancy.published_at, profile.max_age_days)
    score += recency
    if recency > 0:
        matched.append(f"свежая публикация (+{recency})")
    else:
        concerns.append("дата публикации старая или не распознана")

    dealbreaker_hits = matched_terms(blob, profile.dealbreakers)
    if dealbreaker_hits:
        penalty = min(35, len(dealbreaker_hits) * 18)
        score -= penalty
        concerns.append("dealbreakers: " + ", ".join(dealbreaker_hits))

    if python_is_core(profile) and "python" not in blob:
        score -= 18
        concerns.append("для Python-профиля в вакансии не видно Python")

    off_stack_hits = off_stack_terms(blob)
    if off_stack_hits and "python" not in blob:
        penalty = min(30, len(off_stack_hits) * 12)
        score -= penalty
        concerns.append("стек уводит от Python: " + ", ".join(off_stack_hits))

    if not vacancy.stack:
        score -= 5
        concerns.append("стек не указан явно")

    return ScoredVacancy(vacancy=vacancy, score=max(0, min(100, score)), matched=matched, concerns=concerns)


def matched_terms(blob: str, terms: list[str]) -> list[str]:
    result = []
    for term in terms:
        normalized = term.lower().strip()
        if normalized and normalized in blob:
            result.append(term)
    return result


def python_is_core(profile: CandidateProfile) -> bool:
    text = " ".join(profile.target_roles + profile.must_have_skills + profile.nice_to_have_skills).lower()
    return "python" in text


def off_stack_terms(blob: str) -> list[str]:
    terms = ["go разработчик", "golang", "1c", "1с", "php", "java", "c#", "c++", "react", "frontend"]
    return [term for term in terms if term in blob]


def best_role_score(title: str, roles: list[str]) -> float:
    if not roles:
        return 0
    scores = []
    for role in roles:
        role_text = role.lower()
        if role_text in title:
            scores.append(1.0)
        else:
            scores.append(SequenceMatcher(None, title, role_text).ratio())
    return max(scores)


def level_matches(level: str, blob: str, levels: list[str]) -> bool:
    level_text = f"{level} {blob}".lower()
    return any(item.lower() in level_text for item in levels)


def location_matches(vacancy: Vacancy, profile: CandidateProfile) -> bool:
    city = vacancy.city.lower()
    work = vacancy.work_format.lower()
    if profile.remote_ok and (vacancy.remote or "remote" in work or "удален" in work or "удалён" in work):
        return True
    return any(location.lower() in city for location in profile.preferred_locations)


def recency_points(raw_date: str, max_age_days: int) -> int:
    parsed = parse_date(raw_date)
    if not parsed:
        return 0
    age = (date.today() - parsed).days
    if age < 0:
        age = 0
    if age > max_age_days:
        return 0
    return max(1, int(10 * (1 - age / max_age_days)))


def parse_date(raw_date: str) -> date | None:
    if not raw_date:
        return None
    candidates = [raw_date[:10], raw_date]
    for candidate in candidates:
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y"]:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None
