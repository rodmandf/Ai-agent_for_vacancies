from __future__ import annotations

from pathlib import Path

from .models import CandidateProfile, ScoredVacancy, VacancyExplanation, ValidationResult
from .storage import RunLogger, now_stamp


def build_report(
    profile: CandidateProfile,
    scored: list[ScoredVacancy],
    explanations: list[VacancyExplanation],
    validation: ValidationResult,
    logger: RunLogger,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    explanation_by_id = {item.vacancy_id: item for item in explanations}
    sources = sorted({item.source for item in validation.valid})

    lines: list[str] = [
        "# Отчет по подбору junior-вакансий",
        "",
        f"Дата запуска: {now_stamp()}",
        "",
        "## Профиль кандидата",
        "",
        f"- Целевые роли: {join_or_dash(profile.target_roles)}",
        f"- Must-have навыки: {join_or_dash(profile.must_have_skills)}",
        f"- Nice-to-have навыки: {join_or_dash(profile.nice_to_have_skills)}",
        f"- Локации: {join_or_dash(profile.preferred_locations)}",
        f"- Удаленка допустима: {'да' if profile.remote_ok else 'нет'}",
        f"- Уровень: {join_or_dash(profile.levels)}",
        f"- Dealbreakers: {join_or_dash(profile.dealbreakers)}",
        "",
        "## Источники и валидация",
        "",
        f"- Источники: {join_or_dash(sources)}",
        f"- Валидных вакансий: {len(validation.valid)}",
        f"- Битых строк: {len(validation.broken_rows)}",
        f"- Дублей удалено: {validation.duplicates}",
    ]

    for warning in validation.warnings:
        lines.append(f"- Предупреждение: {warning}")
    for broken in validation.broken_rows[:8]:
        lines.append(f"- Ошибка строки: {broken}")

    lines.extend(["", "## Рейтинг всех вакансий", ""])
    for index, item in enumerate(scored, start=1):
        vacancy = item.vacancy
        lines.extend(
            [
                f"### {index}. {vacancy.title} - {vacancy.company}",
                "",
                f"- Score: {item.score}/100",
                f"- Источник: {vacancy.source}",
                f"- Формат: {vacancy.work_format}, город: {vacancy.city or 'не указан'}",
                f"- Уровень: {vacancy.level or 'не указан'}",
                f"- Дата публикации: {vacancy.published_at or 'не указана'}",
                f"- URL: {vacancy.url}",
                f"- Совпадения: {join_or_dash(item.matched)}",
                f"- Что смущает: {join_or_dash(item.concerns)}",
                "",
            ]
        )

    lines.extend(["## Подробный топ-5", ""])
    for index, item in enumerate(scored[:5], start=1):
        vacancy = item.vacancy
        explanation = explanation_by_id.get(vacancy.id)
        lines.extend([f"### {index}. {vacancy.title} - {vacancy.company}", ""])
        if explanation:
            lines.extend(
                [
                    f"**Почему подходит:** {explanation.why_fit}",
                    "",
                    f"**Совпавшие требования:** {join_or_dash(explanation.matched_requirements)}",
                    "",
                    f"**Что смущает:** {join_or_dash(explanation.concerns)}",
                    "",
                    f"**Следующий шаг:** {explanation.next_step}",
                    "",
                    f"**Вопросы работодателю:** {join_or_dash(explanation.employer_questions)}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"**Почему подходит:** вакансия набрала {item.score}/100 по детерминированному скорингу.",
                    "",
                    f"**Что смущает:** {join_or_dash(item.concerns)}",
                    "",
                ]
            )

    lines.extend(["## Trace", ""])
    lines.extend(f"- {event}" for event in logger.events)
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.log(f"Markdown-отчет записан: {output_path}.")
    return output_path


def top_summary(scored: list[ScoredVacancy]) -> str:
    if not scored:
        return "Вакансии не найдены."
    lines = ["Топ-3 вакансии:"]
    for index, item in enumerate(scored[:3], start=1):
        lines.append(f"{index}. {item.vacancy.title} — {item.vacancy.company}, {item.score}/100")
    return "\n".join(lines)


def join_or_dash(items: list[str]) -> str:
    return ", ".join(str(item) for item in items if str(item).strip()) or "-"
