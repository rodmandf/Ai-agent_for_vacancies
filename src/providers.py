from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from .config import DATA_DIR, DB_PATH
from .models import CandidateProfile, Vacancy
from .storage import RunLogger


def collect_vacancies(
    profile: CandidateProfile,
    superjob_api_key: str,
    jooble_api_key: str,
    logger: RunLogger,
    minimum: int = 10,
) -> list[Vacancy]:
    vacancies: list[Vacancy] = []
    query = build_query(profile)
    search_queries = build_search_queries(profile)
    location = build_location(profile)

    if superjob_api_key:
        logger.log("Пробую SuperJob API как основной русскоязычный источник вакансий.")
        for search_query in search_queries:
            vacancies.extend(fetch_superjob(superjob_api_key, search_query, location, logger))
            if len(vacancies) >= 150:
                break
        if len(vacancies) < minimum and location:
            logger.log("SuperJob дал мало вакансий по городу, расширяю поиск без города.")
            for search_query in search_queries:
                vacancies.extend(fetch_superjob(superjob_api_key, search_query, "", logger))
                if len(vacancies) >= 150:
                    break
    else:
        logger.log("SUPERJOB_API_KEY не задан, пропускаю SuperJob.")

    if len(vacancies) < minimum and jooble_api_key:
        logger.log("Пробую Jooble API как дополнительный источник вакансий.")
        vacancies.extend(fetch_jooble(jooble_api_key, query, location, logger))
    elif not jooble_api_key:
        logger.log("JOOBLE_API_KEY не задан, пропускаю Jooble.")

    primary_count = len(vacancies)
    if len(vacancies) < minimum:
        logger.log("Пробую Remotive как бесплатный fallback без ключа.")
        vacancies.extend(fetch_remotive(query, logger))

    if primary_count < minimum:
        logger.log("Добавляю локальный SQLite sample как страховку демо и русскоязычный fallback.")
        vacancies.extend(load_local_vacancies(logger))

    logger.log(f"Собрано вакансий до валидации: {len(vacancies)}.")
    return vacancies


def build_query(profile: CandidateProfile) -> str:
    pieces = profile.target_roles[:2] + profile.must_have_skills[:4]
    return " ".join(dict.fromkeys(piece for piece in pieces if piece))


def build_search_queries(profile: CandidateProfile) -> list[str]:
    queries = [
        "Python разработчик",
        "Backend разработчик",
        "Junior Python",
        "стажер Python",
        "разработчик API",
        "Python backend",
        "Backend developer",
        "FastAPI",
        "SQL Python",
    ]
    queries.extend(profile.target_roles[:6])
    queries.extend(profile.must_have_skills[:4])
    result = []
    seen = set()
    for query in queries:
        clean = " ".join(str(query).split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def build_location(profile: CandidateProfile) -> str:
    for location in profile.preferred_locations:
        normalized = location.lower()
        if normalized not in {"remote", "удаленно", "удалённо", "удаленка", "удалёнка"}:
            return location
    return ""


def fetch_superjob(api_key: str, query: str, location: str, logger: RunLogger) -> list[Vacancy]:
    params = {
        "keyword": query,
        "count": "50",
        "page": "0",
        "period": "60",
    }
    if location:
        params["town"] = location
    url = "https://api.superjob.ru/2.0/vacancies/?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "X-Api-App-Id": api_key,
            "User-Agent": "vacancy-agent-demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.log(f"SuperJob недоступен или вернул ошибку: {error}.")
        return []

    jobs = data.get("objects", [])
    place = f", город: {location}" if location else ", без города"
    logger.log(f"SuperJob запрос '{query}'{place} вернул вакансий: {len(jobs)}.")
    vacancies = []
    for item in jobs:
        town = item.get("town") or {}
        place = item.get("place_of_work") or {}
        type_of_work = item.get("type_of_work") or {}
        work_format = " ".join(
            part for part in [str(place.get("title") or ""), str(type_of_work.get("title") or "")] if part
        )
        description = "\n".join(
            part
            for part in [
                item.get("work"),
                item.get("candidat"),
                item.get("compensation"),
                item.get("client", {}).get("description") if isinstance(item.get("client"), dict) else "",
            ]
            if part
        )
        raw = {
            "id": item.get("id"),
            "title": item.get("profession"),
            "company": item.get("firm_name"),
            "description": strip_html(description),
            "city": town.get("title") if isinstance(town, dict) else town,
            "remote": is_remote_text(f"{work_format} {description}"),
            "work_format": work_format or "unknown",
            "level": "",
            "stack": query,
            "published_at": unix_to_iso(item.get("date_published")),
            "url": item.get("link"),
        }
        vacancies.append(Vacancy.from_raw(raw, "superjob"))
    return vacancies


def fetch_jooble(api_key: str, query: str, location: str, logger: RunLogger) -> list[Vacancy]:
    url = f"https://jooble.org/api/{urllib.parse.quote(api_key)}"
    payload = json.dumps({"keywords": query, "location": location, "page": 1}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.log(f"Jooble недоступен или вернул ошибку: {error}.")
        return []

    jobs = data.get("jobs", [])
    logger.log(f"Jooble вернул вакансий: {len(jobs)}.")
    vacancies = []
    for item in jobs:
        raw = {
            "id": item.get("id") or item.get("link"),
            "title": item.get("title"),
            "company": item.get("company"),
            "description": item.get("snippet") or item.get("description"),
            "city": item.get("location"),
            "remote": "remote" in f"{item.get('location', '')} {item.get('title', '')}".lower(),
            "work_format": "remote" if "remote" in f"{item.get('location', '')} {item.get('title', '')}".lower() else "unknown",
            "level": item.get("type") or "",
            "stack": query,
            "published_at": item.get("updated") or item.get("date") or date.today().isoformat(),
            "url": item.get("link"),
        }
        vacancies.append(Vacancy.from_raw(raw, "jooble"))
    return vacancies


def fetch_remotive(query: str, logger: RunLogger) -> list[Vacancy]:
    params = urllib.parse.urlencode({"search": query, "limit": "20"})
    url = f"https://remotive.com/api/remote-jobs?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "vacancy-agent-demo/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.log(f"Remotive недоступен или вернул ошибку: {error}.")
        return []

    jobs = data.get("jobs", [])
    logger.log(f"Remotive вернул вакансий: {len(jobs)}.")
    vacancies = []
    for item in jobs:
        tags = item.get("tags") or []
        raw = {
            "id": item.get("id"),
            "title": item.get("title"),
            "company": item.get("company_name"),
            "description": strip_html(item.get("description", "")),
            "city": item.get("candidate_required_location") or "Remote",
            "remote": True,
            "work_format": "remote",
            "level": "",
            "stack": tags,
            "published_at": item.get("publication_date", "")[:10],
            "url": item.get("url"),
        }
        vacancies.append(Vacancy.from_raw(raw, "remotive"))
    return vacancies


def load_local_vacancies(logger: RunLogger) -> list[Vacancy]:
    seed_path = DATA_DIR / "sample_vacancies.sql"
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            connection.executescript(seed_path.read_text(encoding="utf-8"))
            rows = connection.execute(
                """
                SELECT id, title, company, description, city, remote, work_format,
                       level, stack, published_at, url, source
                FROM local_vacancies
                ORDER BY published_at DESC, id ASC
                """
            ).fetchall()
    except (OSError, sqlite3.Error) as error:
        logger.log(f"Локальный SQLite fallback не прочитан: {error}.")
        return []

    logger.log(f"Локальный SQLite fallback вернул вакансий: {len(rows)}.")
    return [
        Vacancy.from_raw(
            {
                "id": row["id"],
                "title": row["title"],
                "company": row["company"],
                "description": row["description"],
                "city": row["city"],
                "remote": bool(row["remote"]),
                "work_format": row["work_format"],
                "level": row["level"],
                "stack": row["stack"],
                "published_at": row["published_at"],
                "url": row["url"],
            },
            row["source"],
        )
        for row in rows
    ]


def strip_html(text: str) -> str:
    result = []
    inside_tag = False
    for char in text:
        if char == "<":
            inside_tag = True
            result.append(" ")
            continue
        if char == ">":
            inside_tag = False
            continue
        if not inside_tag:
            result.append(char)
    return " ".join("".join(result).split())


def is_remote_text(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ["remote", "удален", "удалён", "дистанц"])


def unix_to_iso(value: object) -> str:
    try:
        if value is None:
            return ""
        return datetime.fromtimestamp(int(value)).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return str(value or "")
