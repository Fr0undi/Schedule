"""Обработчик загрузки PDF-файлов с расписанием от администратора"""

from pathlib import Path

from aiogram import Router, F

from aiogram.types import Message

from bot.config import settings

from bot.logger import get_logger

from bot.services.pdf_parser import parse_pdf
from bot.services.storage import save_schedule


logger = get_logger(__name__)

router = Router()


@router.message(F.document, F.chat.type == "private")
async def handle_pdf_upload(message: Message) -> None:
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для загрузки расписания.")
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        await message.answer("📄 Отправьте файл в формате PDF.")
        return

    status_msg = await message.answer("⏳ Обрабатываю PDF...")

    try:
        data_dir = Path(settings.DATA_DIR)
        data_dir.mkdir(parents = True, exist_ok = True)
        file_path = data_dir / doc.file_name

        file = await message.bot.download(doc.file_id, destination = str(file_path))
        if file:
            file.close()

        logger.info("PDF скачан: %s", file_path)

        lessons = parse_pdf(str(file_path), settings.GROUP_NAME)

        if not lessons:
            await status_msg.edit_text(
                "❌ Не удалось разобрать PDF. "
                f"Группа «{settings.GROUP_NAME}» не найдена или таблица пуста.\n"
                "Подробности в логах."
            )
            return

        save_schedule(lessons)

        await status_msg.edit_text(
            f"✅ Расписание обновлено!\n"
            f"Группа: {settings.GROUP_NAME}\n"
            f"Загружено пар: {len(lessons)}"
        )
        logger.info("Расписание обновлено: %d пар", len(lessons))

    except Exception:
        logger.exception("Ошибка при обработке PDF")
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке PDF. Подробности в логах."
        )
