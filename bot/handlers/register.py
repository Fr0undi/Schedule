"""Регистрация группы в чате: /register, /unregister"""

from aiogram import Router, F

from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import (
    save_group,
    remove_group,
    get_group_by_chat,
    list_available_groups,
    list_groups_filtered,
    load_university,
)

from bot.keyboards.register_kb import (
    register_menu_kb,
    register_forms_kb,
    register_institutes_kb,
    register_levels_kb,
    register_courses_kb,
    register_groups_kb,
    search_results_kb,
)


logger = get_logger(__name__)

router = Router()


class RegisterSearch(StatesGroup):
    waiting_query = State()


async def _is_chat_admin(message: Message) -> bool:
    """Проверить, является ли отправитель админом чата"""

    if message.chat.type == "private":
        return message.from_user.id in settings.ADMIN_IDS

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("creator", "administrator")


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext) -> None:
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

    await state.clear()
    await message.answer(
        "📋 Выберите способ поиска группы:",
        reply_markup = register_menu_kb(),
    )


# --- Навигация ---

@router.callback_query(F.data == "rg:menu")
async def cb_register_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Вернуться в главное меню регистрации"""

    await state.clear()
    await callback.message.edit_text(
        "📋 Выберите способ поиска группы:",
        reply_markup = register_menu_kb(),
    )
    await callback.answer()


# --- Поиск по названию ---

@router.callback_query(F.data == "rg:search")
async def cb_register_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать поиск по названию"""

    await state.set_state(RegisterSearch.waiting_query)
    await callback.message.edit_text(
        "🔍 Введите название группы (или часть названия):",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = [
            [InlineKeyboardButton(text = "« Назад", callback_data = "rg:menu")],
        ]),
    )
    await callback.answer()


@router.message(RegisterSearch.waiting_query, F.text)
async def fsm_search_query(message: Message, state: FSMContext) -> None:
    """FSM: поиск групп по введённому тексту"""

    query = message.text.strip().lower()
    all_groups = list_available_groups()

    results = [g for g in all_groups if query in g.lower()]

    await state.clear()

    if not results:
        await message.answer(
            f"❌ Группы по запросу «{message.text.strip()}» не найдены",
            reply_markup = register_menu_kb(),
        )
        return

    if len(results) > 20:
        results = results[:20]

    await message.answer(
        f"🔍 Найдено групп: {len(results)}",
        reply_markup = search_results_kb(results),
    )


# --- Пошаговый выбор ---

@router.callback_query(F.data == "rg:step")
async def cb_register_step(callback: CallbackQuery) -> None:
    """Пошаговый выбор: формы обучения"""

    uni = load_university()
    forms = uni.get("forms", [])

    if not forms:
        await callback.answer("Структура университета не настроена", show_alert = True)
        return

    await callback.message.edit_text(
        "📋 Выберите форму обучения:",
        reply_markup = register_forms_kb(forms),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rg:f:"))
async def cb_register_form(callback: CallbackQuery) -> None:
    """Форма выбрана → институты"""

    form_code = callback.data.split(":")[2]
    uni = load_university()
    form = next((f for f in uni.get("forms", []) if f["code"] == form_code), None)

    if not form:
        await callback.answer("Форма не найдена", show_alert = True)
        return

    await callback.message.edit_text(
        "🏛 Выберите институт:",
        reply_markup = register_institutes_kb(form["institutes"], form_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rg:i:"))
async def cb_register_institute(callback: CallbackQuery) -> None:
    """Институт выбран → уровни"""

    parts = callback.data.split(":")
    form_code, inst_code = parts[2], parts[3]

    uni = load_university()
    form = next((f for f in uni.get("forms", []) if f["code"] == form_code), None)
    if not form:
        await callback.answer("Форма не найдена", show_alert = True)
        return

    inst = next((i for i in form["institutes"] if i["code"] == inst_code), None)
    if not inst:
        await callback.answer("Институт не найден", show_alert = True)
        return

    await callback.message.edit_text(
        "📚 Выберите уровень обучения:",
        reply_markup = register_levels_kb(inst["levels"], form_code, inst_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rg:l:"))
async def cb_register_level(callback: CallbackQuery) -> None:
    """Уровень выбран → курсы"""

    parts = callback.data.split(":")
    form_code, inst_code, level_code = parts[2], parts[3], parts[4]

    uni = load_university()
    form = next((f for f in uni.get("forms", []) if f["code"] == form_code), None)
    if not form:
        await callback.answer("Форма не найдена", show_alert = True)
        return

    inst = next((i for i in form["institutes"] if i["code"] == inst_code), None)
    if not inst:
        await callback.answer("Институт не найден", show_alert = True)
        return

    level = next((l for l in inst["levels"] if l["code"] == level_code), None)
    if not level:
        await callback.answer("Уровень не найден", show_alert = True)
        return

    await callback.message.edit_text(
        "🎓 Выберите курс:",
        reply_markup = register_courses_kb(level["courses"], form_code, inst_code, level_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rg:c:"))
async def cb_register_course(callback: CallbackQuery) -> None:
    """Курс выбран → показать группы"""

    parts = callback.data.split(":")
    form_code, inst_code, level_code = parts[2], parts[3], parts[4]
    course = int(parts[5])

    groups = list_groups_filtered(
        form = form_code,
        institute = inst_code,
        level = level_code,
        course = course,
    )

    if not groups:
        await callback.message.edit_text(
            "📭 Нет доступных групп для выбранных параметров\n"
            "Возможно, расписание ещё не загружено",
            reply_markup = register_menu_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Выберите группу:",
        reply_markup = register_groups_kb(groups),
    )
    await callback.answer()


# --- Выбор группы ---

@router.callback_query(F.data.startswith("rg:g:"))
async def cb_register_group(callback: CallbackQuery) -> None:
    """Группа выбрана → привязать к чату"""

    group_name = callback.data[5:]

    # Проверить права админа
    if callback.message.chat.type != "private":
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
