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


async def _get_admin_groups(message: Message) -> list[str]:
    """Получить список групп, в чатах которых пользователь является админом"""

    groups = load_groups()
    admin_groups = []
    for chat_id, config in groups.items():
        try:
            member = await message.bot.get_chat_member(chat_id, message.from_user.id)
            if member.status in ("creator", "administrator"):
                admin_groups.append(config["group_name"])
        except Exception:
            continue
    return admin_groups


@router.message(F.document, F.chat.type == "private")
async def handle_pdf_upload(message: Message) -> None:
    is_global_admin = message.from_user.id in settings.ADMIN_IDS
    admin_groups = [] if is_global_admin else await _get_admin_groups(message)

    if not is_global_admin and not admin_groups:
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

        if is_global_admin:
            allowed_groups = all_groups
        else:
            allowed_groups = {
                name: lessons for name, lessons in all_groups.items()
                if name in admin_groups
            }

        if not allowed_groups:
            found = ", ".join(all_groups.keys())
            await status_msg.edit_text(
                f"⚠️ В PDF найдены группы, но ни одна не совпадает с вашими\n"
                f"Найдены: {found}\n"
                f"Ваши группы: {', '.join(admin_groups)}"
            )
            return

        for group_name, lessons in allowed_groups.items():
            save_schedule(group_name, lessons)

        group_list = "\n".join(
            f"  • {name}: {len(lessons)} пар"
            for name, lessons in allowed_groups.items()
        )

        await status_msg.edit_text(
            f"✅ Расписание обновлено!\n"
            f"Обновлено групп: {len(allowed_groups)}\n\n"
            f"{group_list}"
        )
        logger.info("Расписание обновлено для %d групп", len(allowed_groups))

    except Exception:
        logger.exception("Ошибка при обработке PDF")
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке PDF. Подробности в логах"
        )
