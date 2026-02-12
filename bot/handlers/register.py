"""Регистрация группы в чате: /register, /unregister"""

from aiogram import Router, F

from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import (
    save_group,
    remove_group,
    get_group_by_chat,
    list_available_groups,
)

from bot.keyboards.inline import group_selection_keyboard


logger = get_logger(__name__)

router = Router()


async def _is_chat_admin(message: Message) -> bool:
    """Проверить, является ли отправитель админом чата"""

    if message.chat.type == "private":
        return message.from_user.id in settings.ADMIN_IDS

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("creator", "administrator")


@router.message(Command("register"))
async def cmd_register(message: Message) -> None:
    if not await _is_chat_admin(message):
        await message.answer("⛔ Только администратор чата может регистрировать группу")
        return

    existing = get_group_by_chat(message.chat.id)
    if existing:
        await message.answer(
            f"Этот чат уже привязан к группе <b>{existing['group_name']}</b>\n"
            "Используйте /unregister чтобы отвязать"
        )
        return

    groups = list_available_groups()
    if not groups:
        await message.answer(
            "📭 Нет доступных групп\n"
            "Сначала загрузите PDF с расписанием боту в личные сообщения"
        )
        return

    await message.answer(
        "Выберите вашу группу:",
        reply_markup = group_selection_keyboard(groups),
    )


@router.callback_query(F.data.startswith("reg:"))
async def on_group_selected(callback: CallbackQuery) -> None:
    group_name = callback.data[4:]

    member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    if member.status not in ("creator", "administrator") and callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Только админ может выбирать группу", show_alert = True)
        return

    save_group(
        chat_id = callback.message.chat.id,
        group_name = group_name,
        semester_start = settings.SEMESTER_START,
        registered_by = callback.from_user.id,
    )

    await callback.message.edit_text(f"✅ Группа <b>{group_name}</b> привязана к этому чату")
    logger.info(
        "Группа [%s] зарегистрирована в чате %d пользователем %d",
        group_name, callback.message.chat.id, callback.from_user.id,
    )


@router.message(Command("unregister"))
async def cmd_unregister(message: Message) -> None:
    if not await _is_chat_admin(message):
        await message.answer("⛔ Только администратор чата может отвязать группу")
        return

    if remove_group(message.chat.id):
        await message.answer("✅ Группа отвязана от этого чата")
    else:
        await message.answer("Этот чат не привязан ни к одной группе")
