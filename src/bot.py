from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .config import ensure_dirs, get_settings
from .groq_agent import GroqAgent
from .providers import collect_vacancies
from .report import build_report, top_summary
from .scoring import score_vacancies, validate_vacancies
from .storage import RunLogger, load_user, reset_user, save_user


logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Привет! Я помогу подобрать junior-вакансии под резюме.\n\n"
    "Команды:\n"
    "/resume — отправить или обновить резюме\n"
    "/criteria — отправить критерии подбора\n"
    "/find — найти и ранжировать вакансии\n"
    "/report — прислать последний отчет\n"
    "/reset — очистить память\n\n"
    "Можно написать текст после команды или отправить .md/.txt файл после выбора команды."
)


def run_workflow(resume: str, criteria: str, chat_id: str = "dry-run") -> tuple[Path, str]:
    ensure_dirs()
    settings = get_settings()
    log_path = settings.output_dir / "run.log"
    report_path = settings.output_dir / "report.md"
    logger = RunLogger(log_path)

    logger.log(f"Старт workflow для chat_id={chat_id}.")
    if not resume.strip():
        logger.log("Резюме пустое, использую sample_resume.md.")
        resume = (settings.data_dir / "sample_resume.md").read_text(encoding="utf-8")
    if not criteria.strip() and chat_id == "dry-run":
        logger.log("Критерии пустые в dry-run, использую criteria.md.")
        criteria = (settings.data_dir.parent / "criteria.md").read_text(encoding="utf-8")
    elif not criteria.strip():
        logger.log("Критерии пустые, извлекаю профиль только из резюме пользователя.")

    agent = GroqAgent(settings.groq_api_key, settings.groq_model, logger)
    profile = agent.extract_profile(resume, criteria)
    logger.log("Профиль кандидата готов.")

    vacancies = collect_vacancies(profile, settings.superjob_api_key, settings.jooble_api_key, logger)
    validation = validate_vacancies(vacancies)
    logger.log(
        f"Валидация: valid={len(validation.valid)}, broken={len(validation.broken_rows)}, "
        f"duplicates={validation.duplicates}."
    )

    scored = score_vacancies(validation.valid, profile)
    logger.log(f"Скоринг завершен, ранжировано вакансий: {len(scored)}.")
    explanations = agent.explain_top(profile, scored)
    build_report(profile, scored, explanations, validation, logger, report_path)
    return report_path, top_summary(scored)


async def run_bot() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Заполните .env или используйте --dry-run.")

    try:
        from aiogram import Bot, Dispatcher, F
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.exceptions import TelegramNetworkError
        from aiogram.filters import Command
        from aiogram.types import FSInputFile, Message
    except ImportError as error:
        raise RuntimeError("Не установлен aiogram. Выполните: pip install -r requirements.txt") from error

    session = AiohttpSession(proxy=settings.telegram_proxy_url) if settings.telegram_proxy_url else None
    bot = Bot(token=settings.telegram_bot_token, session=session)
    dp = Dispatcher()
    if settings.telegram_proxy_url:
        logger.info("Telegram proxy включен через TELEGRAM_PROXY_URL.")

    async def read_document_text(message: Message) -> str:
        if not message.document:
            return ""
        filename = message.document.file_name or ""
        if not filename.lower().endswith((".md", ".txt")):
            await message.answer("Пока принимаю только .md или .txt файлы.")
            return ""
        file = await bot.get_file(message.document.file_id)
        buffer = await bot.download_file(file.file_path or "")
        raw = buffer.read()
        return raw.decode("utf-8", errors="replace")

    async def save_field(message: Message, field: str, value: str) -> None:
        data = load_user(message.chat.id)
        data[field] = value.strip()
        data["pending_action"] = ""
        data.setdefault("trace", []).append(f"Обновлено поле {field}.")
        save_user(message.chat.id, data)
        label = "резюме" if field == "resume" else "критерии"
        await message.answer(f"Готово, {label} сохранены.")

    @dp.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @dp.message(Command("resume"))
    async def resume_command(message: Message) -> None:
        text = command_payload(message.text or "")
        if text:
            await save_field(message, "resume", text)
            return
        data = load_user(message.chat.id)
        data["pending_action"] = "resume"
        save_user(message.chat.id, data)
        await message.answer("Пришлите резюме следующим сообщением: текстом или файлом .md/.txt.")

    @dp.message(Command("criteria"))
    async def criteria_command(message: Message) -> None:
        text = command_payload(message.text or "")
        if text:
            await save_field(message, "criteria", text)
            return
        data = load_user(message.chat.id)
        data["pending_action"] = "criteria"
        save_user(message.chat.id, data)
        await message.answer("Пришлите критерии следующим сообщением: текстом или файлом .md/.txt.")

    @dp.message(Command("find"))
    async def find_command(message: Message) -> None:
        data = load_user(message.chat.id)
        await message.answer("Запускаю поиск и ранжирование. Это может занять до минуты.")
        try:
            report_path, summary = await asyncio.to_thread(
                run_workflow,
                data.get("resume", ""),
                data.get("criteria", ""),
                str(message.chat.id),
            )
            data["last_report"] = str(report_path)
            data.setdefault("trace", []).append("Сгенерирован новый отчет.")
            save_user(message.chat.id, data)
            await message.answer(summary)
            await message.answer_document(
                FSInputFile(report_path, filename="report.md"),
                caption="Готово: отчет в Markdown.",
            )
        except Exception as error:
            await message.answer(f"Не получилось собрать отчет: {error}")

    @dp.message(Command("report"))
    async def report_command(message: Message) -> None:
        data = load_user(message.chat.id)
        path = Path(data.get("last_report") or settings.output_dir / "report.md")
        if not path.exists():
            await message.answer("Последний отчет не найден. Запустите /find.")
            return
        await message.answer_document(FSInputFile(path, filename="report.md"), caption="Последний отчет.")

    @dp.message(Command("reset"))
    async def reset_command(message: Message) -> None:
        reset_user(message.chat.id)
        await message.answer("Память очищена.")

    @dp.message(F.document)
    async def document_message(message: Message) -> None:
        data = load_user(message.chat.id)
        field = data.get("pending_action")
        if field not in {"resume", "criteria"}:
            await message.answer("Сначала выберите /resume или /criteria, затем отправьте файл.")
            return
        text = await read_document_text(message)
        if text:
            await save_field(message, field, text)

    @dp.message(F.text)
    async def text_message(message: Message) -> None:
        data = load_user(message.chat.id)
        field = data.get("pending_action")
        if field in {"resume", "criteria"}:
            await save_field(message, field, message.text or "")
            return
        await message.answer("Я не понял сообщение. Используйте /start для списка команд.")

    try:
        logger.info("Telegram-бот запущен, polling активен.")
        await dp.start_polling(bot)
    except TelegramNetworkError as error:
        raise RuntimeError(
            "Бот не смог подключиться к api.telegram.org. "
            "Проверьте VPN/proxy и TELEGRAM_PROXY_URL в .env."
        ) from error


def command_payload(text: str) -> str:
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram-бот для подбора junior-вакансий.")
    parser.add_argument("--dry-run", action="store_true", help="Запустить workflow без Telegram.")
    parser.add_argument("--resume", default="", help="Путь к резюме для dry-run.")
    parser.add_argument("--criteria", default="", help="Путь к критериям для dry-run.")
    return parser.parse_args()


def read_optional_file(path: str) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.dry_run:
        report_path, summary = run_workflow(read_optional_file(args.resume), read_optional_file(args.criteria))
        print(summary)
        print(f"Отчет: {report_path}")
        return
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
