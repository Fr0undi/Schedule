"""Обработчик загрузки PDF-файлов с расписанием от администратора"""

from pathlib import Path

from aiogram import Router, F

from aiogram.types import Message

from bot.config import settings

from bot.logger import get_logger

from bot.services.pdf_parser import parse_pdf_all_groups
from bot.services.storage import save_schedule, load_groups


logger = get_logger(__name__)

router = Router()


async def _is_any_chat_admin(message: Message) -> bool:
    """Проверить, является ли пользователь админом хотя бы в одном зарегистрированном чате"""

    groups = load_groups()
    for chat_id in groups:
        try:
            member = await message.bot.get_chat_member(chat_id, message.from_user.id)
            if member.status in ("creator", "administrator"):
                return True
        except Exception:
            continue
    return False


@router.message(F.document, F.chat.type == "private")
async def handle_pdf_upload(message: Message) -> None:
    if message.from_user.id not in settings.ADMIN_IDS and not await _is_any_chat_admin(message):
        await message.answer("⛔ У вас нет прав для загрузки расписания")
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        await message.answer("📄 Отправьте файл в формате PDF")
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

        all_groups = parse_pdf_all_groups(str(file_path))

        if not all_groups:
            await status_msg.edit_text(
                "❌ Не удалось разобрать PDF\n"
                "Группы не найдены или таблица пуста\n"
                "Подробности в логах"
            )
            return

        for group_name, lessons in all_groups.items():
            save_schedule(group_name, lessons)

        group_list = "\n".join(
            f"  • {name}: {len(lessons)} пар"
            for name, lessons in all_groups.items()
        )

        await status_msg.edit_text(
            f"✅ Расписание обновлено!\n"
            f"Найдено групп: {len(all_groups)}\n\n"
            f"{group_list}"
        )
        logger.info("Расписание обновлено для %d групп", len(all_groups))

    except Exception:
        logger.exception("Ошибка при обработке PDF")
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке PDF. Подробности в логах"
        )
