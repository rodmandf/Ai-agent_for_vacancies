from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .models import CandidateProfile, ScoredVacancy, VacancyExplanation
from .scoring import parse_criteria
from .storage import RunLogger


class GroqAgent:
    def __init__(self, api_key: str, model: str, logger: RunLogger) -> None:
        self.api_key = api_key
        self.model = model
        self.logger = logger

    def extract_profile(self, resume: str, criteria: str) -> CandidateProfile:
        fallback = parse_criteria(criteria, resume)
        if not self.api_key:
            self.logger.log("GROQ_API_KEY не задан, профиль извлечен эвристически.")
            return fallback

        prompt = (
            "Ты агент карьерного подбора. Извлеки профиль кандидата из резюме и критериев. "
            "Ответь только JSON с ключами: target_roles, must_have_skills, nice_to_have_skills, "
            "preferred_locations, remote_ok, levels, max_age_days, dealbreakers, summary.\n\n"
            f"Резюме:\n{resume[:5000]}\n\nКритерии:\n{criteria[:3000]}"
        )
        data = self._chat_json(prompt)
        if not data:
            self.logger.log("Groq не извлек профиль, использую эвристику.")
            return fallback

        self.logger.log("Профиль кандидата извлечен через Groq.")
        return CandidateProfile(
            target_roles=as_list(data.get("target_roles")) or fallback.target_roles,
            must_have_skills=as_list(data.get("must_have_skills")) or fallback.must_have_skills,
            nice_to_have_skills=as_list(data.get("nice_to_have_skills")) or fallback.nice_to_have_skills,
            preferred_locations=as_list(data.get("preferred_locations")) or fallback.preferred_locations,
            remote_ok=bool(data.get("remote_ok", fallback.remote_ok)),
            levels=as_list(data.get("levels")) or fallback.levels,
            max_age_days=int(data.get("max_age_days") or fallback.max_age_days),
            dealbreakers=as_list(data.get("dealbreakers")) or fallback.dealbreakers,
            summary=str(data.get("summary") or fallback.summary),
        )

    def explain_top(self, profile: CandidateProfile, scored: list[ScoredVacancy]) -> list[VacancyExplanation]:
        top = scored[:5]
        if not self.api_key:
            self.logger.log("GROQ_API_KEY не задан, объяснения топ-5 созданы эвристически.")
            return [heuristic_explanation(item) for item in top]

        payload = [
            {
                "id": item.vacancy.id,
                "title": item.vacancy.title,
                "company": item.vacancy.company,
                "description": item.vacancy.description[:1200],
                "score": item.score,
                "matched": item.matched,
                "concerns": item.concerns,
            }
            for item in top
        ]
        prompt = (
            "Ты карьерный агент для junior-кандидата. Объясни топ-5 вакансий на русском. "
            "Ответь только JSON-массивом объектов с ключами: vacancy_id, why_fit, "
            "matched_requirements, concerns, next_step, employer_questions. "
            "Будь конкретным и не выдумывай факты вне описания.\n\n"
            f"Профиль:\n{json.dumps(profile.__dict__, ensure_ascii=False)}\n\n"
            f"Вакансии:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        data = self._chat_json(prompt)
        if not isinstance(data, list):
            self.logger.log("Groq не вернул корректные объяснения, использую эвристику.")
            return [heuristic_explanation(item) for item in top]

        explanations: list[VacancyExplanation] = []
        for index, item in enumerate(top):
            raw = data[index] if index < len(data) and isinstance(data[index], dict) else {}
            explanations.append(
                VacancyExplanation(
                    vacancy_id=str(raw.get("vacancy_id") or item.vacancy.id),
                    why_fit=str(raw.get("why_fit") or "Вакансия хорошо совпадает с профилем по скорингу."),
                    matched_requirements=as_list(raw.get("matched_requirements")) or item.matched,
                    concerns=as_list(raw.get("concerns")) or item.concerns,
                    next_step=str(raw.get("next_step") or "Откликнуться и приложить проекты на Python/API."),
                    employer_questions=as_list(raw.get("employer_questions"))
                    or ["Есть ли менторинг для junior?", "Какие задачи будут в первые 2 недели?"],
                )
            )
        self.logger.log("Объяснения топ-5 созданы через Groq.")
        return explanations

    def _chat_json(self, prompt: str) -> Any:
        messages = [
            {"role": "system", "content": "Отвечай валидным JSON без markdown."},
            {"role": "user", "content": prompt},
        ]
        try:
            payload = json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "vacancy-agent-demo/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return json.loads(extract_json(content))
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, OSError) as error:
            self.logger.log(f"Groq HTTP-запрос не сработал: {error}.")
            return None


def heuristic_explanation(item: ScoredVacancy) -> VacancyExplanation:
    concerns = item.concerns or ["Явных рисков мало, но стоит проверить детали команды и задач."]
    return VacancyExplanation(
        vacancy_id=item.vacancy.id,
        why_fit=f"Вакансия набрала {item.score}/100: совпадают роль, стек или формат работы.",
        matched_requirements=item.matched or ["Есть общее совпадение с профилем кандидата."],
        concerns=concerns,
        next_step="Откликнуться, подсветить совпадающие навыки и приложить 1-2 релевантных проекта.",
        employer_questions=[
            "Какие задачи будут у junior в первый месяц?",
            "Будет ли наставник или code review?",
            "Какие навыки важнее всего для успешного старта?",
        ],
    )


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    return [str(value)]


def extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start_object = text.find("{")
    start_array = text.find("[")
    starts = [pos for pos in [start_object, start_array] if pos >= 0]
    if not starts:
        return text
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start : end + 1]
