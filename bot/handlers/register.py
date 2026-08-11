"""Регистрация группы в чате: /register, /unregister + создание группы с нуля"""

import re
from urllib.parse import quote

from aiogram import Router, F

from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    MenuButtonWebApp, MenuButtonDefault, WebAppInfo, ForceReply,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import (
    save_group,
    save_teacher_binding,
    save_schedule,
    remove_group,
    get_group_by_chat,
    list_available_groups,
    list_available_teachers,
    list_groups_filtered,
    load_university,
    _find_schedule_path,
    _normalize_teacher,
)

from bot.keyboards.register_kb import (
    register_menu_kb,
    register_forms_kb,
    register_institutes_kb,
    register_levels_kb,
    register_courses_kb,
    register_groups_kb,
    search_results_kb,
    teacher_search_results_kb,
)


logger = get_logger(__name__)

router = Router()


class RegisterSearch(StatesGroup):
    waiting_query = State()


class RegisterTeacherSearch(StatesGroup):
    waiting_query = State()


class RegisterCreate(StatesGroup):
    waiting_name = State()


def _is_global_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


async def _is_chat_admin(message: Message) -> bool:
    """Проверить, является ли отправитель админом чата"""

    if message.chat.type == "private":
        return True

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("creator", "administrator")


def _menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Меню /register с учётом прав"""

    return register_menu_kb(show_create = _is_global_admin(user_id))


async def _set_menu_button(bot, chat_id: int, group_name: str) -> None:
    """Установить Menu Button с мини-приложением для чата"""

    if not settings.WEBAPP_BASE_URL.startswith("https://"):
        return
    url = f"{settings.WEBAPP_BASE_URL}?group={quote(group_name)}"
    try:
        await bot.set_chat_menu_button(
            chat_id = chat_id,
            menu_button = MenuButtonWebApp(
                text = "Расписание",
                web_app = WebAppInfo(url = url),
            ),
        )
    except Exception:
        logger.warning("Не удалось установить menu button для чата %d", chat_id)


async def _set_teacher_menu_button(bot, chat_id: int, teacher_name: str) -> None:
    """Установить Menu Button с расписанием преподавателя"""

    if not settings.WEBAPP_BASE_URL.startswith("https://"):
        return
    url = f"{settings.WEBAPP_BASE_URL}/teachers?name={quote(teacher_name)}"
    try:
        await bot.set_chat_menu_button(
            chat_id = chat_id,
            menu_button = MenuButtonWebApp(
                text = "Расписание",
                web_app = WebAppInfo(url = url),
            ),
        )
    except Exception:
        logger.warning("Не удалось установить menu button для чата %d", chat_id)


async def _reset_menu_button(bot, chat_id: int) -> None:
    """Сбросить Menu Button на стандартную"""

    try:
        await bot.set_chat_menu_button(
            chat_id = chat_id,
            menu_button = MenuButtonDefault(),
        )
    except Exception:
        logger.warning("Не удалось сбросить menu button для чата %d", chat_id)


@router.message(F.chat.type == "private", F.text == "📋 Привязка")
@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext) -> None:
    if not await _is_chat_admin(message):
        await message.answer("⛔ Только администратор чата может менять привязку")
        return

    existing = get_group_by_chat(message.chat.id)
    if existing:
        bound = existing.get("teacher_name") or existing.get("group_name", "")
        label = "преподавателю" if existing.get("teacher_name") else "группе"
        await message.answer(
            f"Этот чат уже привязан к {label} <b>{bound}</b>\n"
            "Используйте /unregister чтобы отвязать"
        )
        return

    await state.clear()

    await message.answer(
        "📋 Выберите, что привязать к чату:",
        reply_markup = _menu_kb(message.from_user.id),
    )


# --- Навигация ---

@router.callback_query(F.data == "rg:menu")
async def cb_register_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Вернуться в главное меню регистрации"""

    await state.clear()
    await callback.message.edit_text(
        "📋 Выберите, что привязать к чату:",
        reply_markup = _menu_kb(callback.from_user.id),
    )
    await callback.answer()


# --- Поиск по названию ---

@router.callback_query(F.data == "rg:search")
async def cb_register_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать поиск по названию"""

    await state.set_state(RegisterSearch.waiting_query)

    # В группах бот не видит обычные сообщения (privacy mode).
    # ForceReply заставляет клиент показать reply-интерфейс,
    # а ответ на сообщение бота бот получает всегда.
    if callback.message.chat.type != "private":
        await callback.message.edit_text(
            "🔍 Введите название группы.\n"
            "Для отмены — /register",
        )
        await callback.message.answer(
            "↩️ Ответьте на это сообщение названием группы:",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await callback.message.edit_text(
            "🔍 Введите название группы:",
            reply_markup = InlineKeyboardMarkup(inline_keyboard = [
                [InlineKeyboardButton(text = "« Назад", callback_data = "rg:menu")],
            ]),
        )
    await callback.answer()


def _normalize(text: str) -> str:
    """Убрать пробелы, дефисы и привести к нижнему регистру для нечёткого поиска"""

    return re.sub(r"[\s\-]+", "", text).lower()


@router.message(RegisterSearch.waiting_query, F.text)
async def fsm_search_query(message: Message, state: FSMContext) -> None:
    """FSM: поиск групп по введённому тексту"""

    query = message.text.strip().lower()
    query_norm = _normalize(query)
    all_groups = list_available_groups()

    results = [
        g for g in all_groups
        if query in g.lower() or query_norm in _normalize(g)
    ]

    await state.clear()

    if not results:
        await message.answer(
            f"❌ Группы по запросу «{message.text.strip()}» не найдены",
            reply_markup = _menu_kb(message.from_user.id),
        )
        return

    if len(results) > 20:
        results = results[:20]

    await message.answer(
        f"🔍 Найдено групп: {len(results)}",
        reply_markup = search_results_kb(results),
    )


# --- Поиск преподавателя ---

@router.callback_query(F.data == "rg:tsearch")
async def cb_register_teacher_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать поиск преподавателя"""

    await state.set_state(RegisterTeacherSearch.waiting_query)

    if callback.message.chat.type != "private":
        await callback.message.edit_text(
            "🔍 Введите фамилию преподавателя.\n"
            "Для отмены — /register",
        )
        await callback.message.answer(
            "↩️ Ответьте на это сообщение фамилией преподавателя:",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await callback.message.edit_text(
            "🔍 Введите фамилию преподавателя:",
            reply_markup = InlineKeyboardMarkup(inline_keyboard = [
                [InlineKeyboardButton(text = "« Назад", callback_data = "rg:menu")],
            ]),
        )
    await callback.answer()


@router.message(RegisterTeacherSearch.waiting_query, F.text)
async def fsm_teacher_search_query(message: Message, state: FSMContext) -> None:
    """FSM: поиск преподавателей по введённому тексту"""

    query = message.text.strip().lower()
    query_norm = _normalize(query)
    all_teachers = list_available_teachers()

    results = [
        t for t in all_teachers
        if query in t.lower() or query_norm in _normalize(t)
    ]

    await state.clear()

    if not results:
        await message.answer(
            f"❌ Преподаватели по запросу «{message.text.strip()}» не найдены",
            reply_markup = _menu_kb(message.from_user.id),
        )
        return

    if len(results) > 20:
        results = results[:20]

    await message.answer(
        f"🔍 Найдено преподавателей: {len(results)}",
        reply_markup = teacher_search_results_kb(results),
    )


@router.callback_query(F.data.startswith("rg:t:"))
async def cb_register_teacher(callback: CallbackQuery) -> None:
    """Преподаватель выбран → привязать к чату"""

    teacher_name = callback.data[5:]

    # Проверить права админа
    if callback.message.chat.type != "private":
        member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
        if member.status not in ("creator", "administrator") and callback.from_user.id not in settings.ADMIN_IDS:
            await callback.answer("⛔ Только админ может привязывать расписание", show_alert = True)
            return

    save_teacher_binding(
        chat_id = callback.message.chat.id,
        teacher_name = teacher_name,
        semester_start = settings.SEMESTER_START,
        registered_by = callback.from_user.id,
    )

    await _set_teacher_menu_button(callback.bot, callback.message.chat.id, teacher_name)

    await callback.message.edit_text(f"✅ Расписание преподавателя <b>{teacher_name}</b> привязано к этому чату")
    logger.info(
        "Преподаватель [%s] зарегистрирован в чате %d пользователем %d",
        teacher_name, callback.message.chat.id, callback.from_user.id,
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
            reply_markup = _menu_kb(callback.from_user.id),
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
            await callback.answer("⛔ Только админ может менять привязку", show_alert = True)
            return

    save_group(
        chat_id = callback.message.chat.id,
        group_name = group_name,
        semester_start = settings.SEMESTER_START,
        registered_by = callback.from_user.id,
    )

    await _set_menu_button(callback.bot, callback.message.chat.id, group_name)

    await callback.message.edit_text(f"✅ Группа <b>{group_name}</b> привязана к этому чату")
    logger.info(
        "Группа [%s] зарегистрирована в чате %d пользователем %d",
        group_name, callback.message.chat.id, callback.from_user.id,
    )


# ===== СОЗДАНИЕ ГРУППЫ С НУЛЯ =====

def _cr_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "Отмена", callback_data = "cr:cancel")],
    ])


@router.callback_query(F.data == "cr:start")
async def cb_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать создание группы"""

    if not _is_global_admin(callback.from_user.id):
        await callback.answer("⛔ Только глобальный админ", show_alert = True)
        return

    await state.set_state(RegisterCreate.waiting_name)

    if callback.message.chat.type != "private":
        await callback.message.edit_text(
            "📝 Введите название группы (например: ДМ 32-25).\n"
            "Для отмены — /register",
        )
        await callback.message.answer(
            "↩️ Ответьте на это сообщение названием группы:",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await callback.message.edit_text(
            "📝 Введите название группы (например: ДМ 32-25):",
            reply_markup = _cr_cancel_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "cr:cancel")
async def cb_create_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания → вернуться в меню"""

    await state.clear()
    await callback.message.edit_text(
        "📋 Выберите способ поиска группы:",
        reply_markup = _menu_kb(callback.from_user.id),
    )
    await callback.answer()


@router.message(RegisterCreate.waiting_name, F.text)
async def fsm_create_name(message: Message, state: FSMContext) -> None:
    """FSM: ввод названия группы → выбор формы"""

    name = message.text.strip()

    if _find_schedule_path(name):
        await message.answer(
            f"⚠️ Группа <b>{name}</b> уже существует\n"
            "Выберите её через поиск или по структуре",
            reply_markup = _menu_kb(message.from_user.id),
        )
        await state.clear()
        return

    await state.update_data(cr_group_name = name)

    uni = load_university()
    forms = uni.get("forms", [])

    if not forms:
        # Нет university.json → создать без метаданных и сразу привязать
        save_schedule(name, [])
        save_group(
            chat_id = message.chat.id,
            group_name = name,
            semester_start = settings.SEMESTER_START,
            registered_by = message.from_user.id,
        )
        await _set_menu_button(message.bot, message.chat.id, name)
        await state.clear()
        await message.answer(
            f"✅ Группа <b>{name}</b> создана и привязана к чату\n"
            "Используйте /edit для добавления пар"
        )
        logger.info("Создана и привязана группа [%s] в чате %d", name, message.chat.id)
        return

    buttons = [
        [InlineKeyboardButton(text = f["name"], callback_data = f"cr:f:{f['code']}")]
        for f in forms
    ]
    buttons.append([InlineKeyboardButton(text = "Отмена", callback_data = "cr:cancel")])

    await state.set_state(None)
    await message.answer(
        f"Группа: <b>{name}</b>\n📋 Выберите форму обучения:",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = buttons),
    )


@router.callback_query(F.data == "cr:forms")
async def cb_create_back_forms(callback: CallbackQuery, state: FSMContext) -> None:
    """Назад к формам"""

    data = await state.get_data()
    name = data.get("cr_group_name", "")

    uni = load_university()
    forms = uni.get("forms", [])

    buttons = [
        [InlineKeyboardButton(text = f["name"], callback_data = f"cr:f:{f['code']}")]
        for f in forms
    ]
    buttons.append([InlineKeyboardButton(text = "Отмена", callback_data = "cr:cancel")])

    await callback.message.edit_text(
        f"Группа: <b>{name}</b>\n📋 Выберите форму обучения:",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cr:f:"))
async def cb_create_form(callback: CallbackQuery, state: FSMContext) -> None:
    """Форма выбрана → институты"""

    form_code = callback.data.split(":")[2]
    await state.update_data(cr_form = form_code)

    uni = load_university()
    form = next((f for f in uni.get("forms", []) if f["code"] == form_code), None)
    if not form:
        await callback.answer("Форма не найдена", show_alert = True)
        return

    buttons = [
        [InlineKeyboardButton(
            text = inst["name"],
            callback_data = f"cr:i:{form_code}:{inst['code']}",
        )]
        for inst in form["institutes"]
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "cr:forms")])

    await callback.message.edit_text(
        "🏛 Выберите институт:",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cr:i:"))
async def cb_create_inst(callback: CallbackQuery, state: FSMContext) -> None:
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

    buttons = [
        [InlineKeyboardButton(
            text = lv["name"],
            callback_data = f"cr:l:{form_code}:{inst_code}:{lv['code']}",
        )]
        for lv in inst["levels"]
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"cr:f:{form_code}")])

    await callback.message.edit_text(
        "📚 Выберите уровень обучения:",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cr:l:"))
async def cb_create_level(callback: CallbackQuery, state: FSMContext) -> None:
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

    level = next((lv for lv in inst["levels"] if lv["code"] == level_code), None)
    if not level:
        await callback.answer("Уровень не найден", show_alert = True)
        return

    buttons = [
        [InlineKeyboardButton(
            text = f"{c} курс",
            callback_data = f"cr:c:{form_code}:{inst_code}:{level_code}:{c}",
        )]
        for c in level["courses"]
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"cr:i:{form_code}:{inst_code}")])

    await callback.message.edit_text(
        "🎓 Выберите курс:",
        reply_markup = InlineKeyboardMarkup(inline_keyboard = buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cr:c:"))
async def cb_create_course(callback: CallbackQuery, state: FSMContext) -> None:
    """Курс выбран → создать группу и привязать к чату"""

    parts = callback.data.split(":")
    form_code, inst_code, level_code = parts[2], parts[3], parts[4]
    course = int(parts[5])

    data = await state.get_data()
    name = data.get("cr_group_name", "")

    if not name:
        await callback.answer("Ошибка: название группы потеряно", show_alert = True)
        return

    # Создать пустое расписание с метаданными
    save_schedule(name, [], form = form_code, institute = inst_code, level = level_code, course = course)

    # Привязать к чату
    save_group(
        chat_id = callback.message.chat.id,
        group_name = name,
        semester_start = settings.SEMESTER_START,
        registered_by = callback.from_user.id,
    )

    await _set_menu_button(callback.bot, callback.message.chat.id, name)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Группа <b>{name}</b> создана и привязана к чату\n"
        "Используйте /edit для добавления пар"
    )
    await callback.answer()
    logger.info(
        "Создана и привязана группа [%s]: %s/%s/%s/%d, чат %d",
        name, form_code, inst_code, level_code, course, callback.message.chat.id,
    )


# --- Unregister ---

@router.message(Command("unregister"))
async def cmd_unregister(message: Message) -> None:
    if not await _is_chat_admin(message):
        await message.answer("⛔ Только администратор чата может снять привязанное расписание")
        return

    if remove_group(message.chat.id, removed_by = message.from_user.id):
        await _reset_menu_button(message.bot, message.chat.id)
        await message.answer("✅ Расписание отвязано")
    else:
        await message.answer("Этот чат ни к чему не привязан")
