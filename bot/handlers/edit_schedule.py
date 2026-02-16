"""Ручное редактирование расписания: /edit (удаление, добавление, изменение пар)"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ForceReply
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.config import settings
from bot.logger import get_logger
from bot.services.storage import load_schedule, save_schedule, get_group_by_chat
from bot.services.formatter import LESSON_TIMES
from bot.keyboards.edit_kb import (
    edit_main_menu_kb,
    edit_days_kb,
    lessons_list_kb,
    delete_confirm_kb,
    add_lesson_number_kb,
    add_week_type_kb,
    add_lesson_type_kb,
    edit_field_kb,
    edit_lesson_type_kb,
    edit_week_type_kb,
    move_day_kb,
    move_number_kb,
    cancel_kb,
    back_to_menu_kb,
)


logger = get_logger(__name__)

router = Router()


DAY_NAMES_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

WEEK_TYPE_MAP = {"b": "both", "o": "odd", "e": "even"}
WEEK_TYPE_DISPLAY = {"both": "обе недели", "odd": "нечётная", "even": "чётная"}

LESSON_TYPE_MAP = {"lk": "Лекция", "pr": "Практика", "lb": "Лабораторная", "dr": "Другое"}

FIELD_NAMES = {
    "sub": "Предмет",
    "typ": "Тип занятия",
    "tch": "Преподаватель",
    "rm": "Аудитория",
    "wt": "Тип недели",
    "dn": "День/номер пары",
}


class EditSchedule(StatesGroup):
    """FSM-состояния для ввода текста"""

    add_subject = State()
    add_teacher = State()
    add_room = State()
    edit_value = State()


# --- Helpers ---

async def _is_chat_admin(message: Message) -> bool:
    """Проверить, является ли отправитель админом чата"""

    if message.chat.type == "private":
        return message.from_user.id in settings.ADMIN_IDS

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("creator", "administrator")


async def _is_callback_admin(callback: CallbackQuery) -> bool:
    """Проверить, является ли нажавший кнопку админом"""

    if callback.message.chat.type == "private":
        return callback.from_user.id in settings.ADMIN_IDS

    member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    return member.status in ("creator", "administrator")


def _format_lesson(lesson: dict) -> str:
    """Форматировать пару для отображения"""

    wt = WEEK_TYPE_DISPLAY.get(lesson["week_type"], "")
    parts = [
        f"<b>{lesson['lesson_number']}. {lesson['time_start']}–{lesson['time_end']}</b>",
        f"📘 {lesson['subject']}",
        f"Тип: {lesson['lesson_type']}",
    ]
    if lesson.get("teacher"):
        parts.append(f"Преподаватель: {lesson['teacher']}")
    if lesson.get("room"):
        parts.append(f"Аудитория: {lesson['room']}")
    parts.append(f"Неделя: {wt}")
    return "\n".join(parts)


def _get_group_name(chat_id: int) -> str | None:
    """Получить название группы по chat_id"""

    group = get_group_by_chat(chat_id)
    return group["group_name"] if group else None


def _verify_lesson(lessons: list[dict], idx: int, expected: dict) -> bool:
    """Проверить что пара по индексу не изменилась"""

    if idx < 0 or idx >= len(lessons):
        return False
    lesson = lessons[idx]
    return (
        lesson["weekday"] == expected["weekday"]
        and lesson["lesson_number"] == expected["lesson_number"]
        and lesson["subject"] == expected["subject"]
    )


# --- Entry point ---

@router.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext) -> None:
    """Команда /edit — главное меню редактирования"""

    if not await _is_chat_admin(message):
        await message.answer("⛔ Только администратор может редактировать расписание")
        return

    group_name = _get_group_name(message.chat.id)
    if not group_name:
        await message.answer("❓ Группа не привязана к этому чату\nИспользуйте /register для привязки")
        return

    await state.clear()
    await state.update_data(group_name = group_name)
    await message.answer(
        f"✏️ Редактирование расписания <b>{group_name}</b>\nВыберите действие:",
        reply_markup = edit_main_menu_kb(),
    )


# --- Navigation ---

@router.callback_query(F.data == "ed:menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню"""

    await state.clear()
    group_name = _get_group_name(callback.message.chat.id)
    if not group_name:
        await callback.message.edit_text("❓ Группа не привязана")
        return

    await state.update_data(group_name = group_name)
    await callback.message.edit_text(
        f"✏️ Редактирование расписания <b>{group_name}</b>\nВыберите действие:",
        reply_markup = edit_main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "ed:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена текущей операции"""

    await state.clear()
    group_name = _get_group_name(callback.message.chat.id)
    await state.update_data(group_name = group_name)
    await callback.message.edit_text(
        f"✏️ Редактирование расписания <b>{group_name}</b>\nВыберите действие:",
        reply_markup = edit_main_menu_kb(),
    )
    await callback.answer("Отменено")


# ===== DELETE FLOW =====

@router.callback_query(F.data == "ed:del")
async def cb_delete_start(callback: CallbackQuery) -> None:
    """Удаление: выбор дня"""

    if not await _is_callback_admin(callback):
        await callback.answer("⛔ Только админ", show_alert = True)
        return

    await callback.message.edit_text(
        "🗑 Удалить пару\nВыберите день:",
        reply_markup = edit_days_kb("ed:d:"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:d:"))
async def cb_delete_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаление: список пар на выбранный день"""

    day = int(callback.data.split(":")[2])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)
    if not group_name:
        await callback.message.edit_text("❓ Группа не привязана")
        return

    lessons = load_schedule(group_name)
    await callback.message.edit_text(
        f"🗑 Удалить пару — {DAY_NAMES_FULL[day - 1]}\nВыберите пару:",
        reply_markup = lessons_list_kb(lessons, day, "ed:dl:", "ed:del"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:dl:"))
async def cb_delete_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаление: подтверждение"""

    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)
    lessons = load_schedule(group_name)

    if idx >= len(lessons):
        await callback.answer("Пара не найдена, попробуйте снова", show_alert = True)
        return

    lesson = lessons[idx]
    await state.update_data(
        del_idx = idx,
        del_weekday = lesson["weekday"],
        del_lesson_number = lesson["lesson_number"],
        del_subject = lesson["subject"],
    )

    await callback.message.edit_text(
        f"🗑 Удалить эту пару?\n\n{_format_lesson(lesson)}",
        reply_markup = delete_confirm_kb(idx, lesson["weekday"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:dc:"))
async def cb_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаление: выполнить"""

    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)
    lessons = load_schedule(group_name)

    expected = {
        "weekday": data.get("del_weekday"),
        "lesson_number": data.get("del_lesson_number"),
        "subject": data.get("del_subject"),
    }

    if not _verify_lesson(lessons, idx, expected):
        await callback.message.edit_text(
            "⚠️ Расписание изменилось, попробуйте снова",
            reply_markup = back_to_menu_kb(),
        )
        await callback.answer()
        return

    removed = lessons.pop(idx)
    save_schedule(group_name, lessons)
    logger.info("Удалена пара [%s]: %s, день %d", group_name, removed["subject"], removed["weekday"])

    await callback.message.edit_text(
        f"✅ Пара удалена: {removed['subject']}",
        reply_markup = back_to_menu_kb(),
    )
    await callback.answer()


# ===== ADD FLOW =====

@router.callback_query(F.data == "ed:add")
async def cb_add_start(callback: CallbackQuery) -> None:
    """Добавление: выбор дня"""

    if not await _is_callback_admin(callback):
        await callback.answer("⛔ Только админ", show_alert = True)
        return

    await callback.message.edit_text(
        "➕ Добавить пару\nВыберите день:",
        reply_markup = edit_days_kb("ed:ad:"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:ad:"))
async def cb_add_day(callback: CallbackQuery) -> None:
    """Добавление: выбор номера пары"""

    day = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        f"➕ Добавить пару — {DAY_NAMES_FULL[day - 1]}\nВыберите номер пары:",
        reply_markup = add_lesson_number_kb(day),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:an:"))
async def cb_add_number(callback: CallbackQuery) -> None:
    """Добавление: выбор типа недели"""

    parts = callback.data.split(":")
    day, num = int(parts[2]), int(parts[3])
    await callback.message.edit_text(
        f"➕ Добавить пару — {DAY_NAMES_FULL[day - 1]}, {num}-я пара\nТип недели:",
        reply_markup = add_week_type_kb(day, num),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:aw:"))
async def cb_add_week_type(callback: CallbackQuery) -> None:
    """Добавление: выбор типа занятия"""

    parts = callback.data.split(":")
    day, num, wt = int(parts[2]), int(parts[3]), parts[4]
    wt_display = WEEK_TYPE_DISPLAY.get(WEEK_TYPE_MAP.get(wt, ""), "")

    await callback.message.edit_text(
        f"➕ {DAY_NAMES_FULL[day - 1]}, {num}-я пара ({wt_display})\nТип занятия:",
        reply_markup = add_lesson_type_kb(day, num, wt),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:at:"))
async def cb_add_lesson_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Добавление: запуск FSM для ввода названия предмета"""

    parts = callback.data.split(":")
    day, num, wt, lt = int(parts[2]), int(parts[3]), parts[4], parts[5]

    await state.update_data(
        add_day = day,
        add_num = num,
        add_week_type = WEEK_TYPE_MAP[wt],
        add_lesson_type = LESSON_TYPE_MAP[lt],
    )
    await state.set_state(EditSchedule.add_subject)

    if callback.message.chat.type != "private":
        await callback.message.edit_text("📝 Введите название предмета:")
        await callback.message.answer(
            "↩️ Ответьте на это сообщение:",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await callback.message.edit_text(
            "📝 Введите название предмета:",
            reply_markup = cancel_kb(),
        )
    await callback.answer()


@router.message(EditSchedule.add_subject, F.text)
async def fsm_add_subject(message: Message, state: FSMContext) -> None:
    """FSM: ввод названия предмета → запрос преподавателя"""

    await state.update_data(add_subject = message.text.strip())
    await state.set_state(EditSchedule.add_teacher)

    if message.chat.type != "private":
        await message.answer(
            "👤 Введите ФИО преподавателя (или <code>-</code> чтобы пропустить):",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await message.answer(
            "👤 Введите ФИО преподавателя\n(или <code>-</code> чтобы пропустить):",
            reply_markup = cancel_kb(),
        )


@router.message(EditSchedule.add_teacher, F.text)
async def fsm_add_teacher(message: Message, state: FSMContext) -> None:
    """FSM: ввод преподавателя → запрос аудитории"""

    teacher = message.text.strip()
    await state.update_data(add_teacher = None if teacher == "-" else teacher)
    await state.set_state(EditSchedule.add_room)

    if message.chat.type != "private":
        await message.answer(
            "🚪 Введите номер аудитории (или <code>-</code> чтобы пропустить):",
            reply_markup = ForceReply(selective = True),
        )
    else:
        await message.answer(
            "🚪 Введите номер аудитории\n(или <code>-</code> чтобы пропустить):",
            reply_markup = cancel_kb(),
        )


@router.message(EditSchedule.add_room, F.text)
async def fsm_add_room(message: Message, state: FSMContext) -> None:
    """FSM: ввод аудитории → создание пары"""

    room = message.text.strip()
    data = await state.get_data()

    group_name = data.get("group_name") or _get_group_name(message.chat.id)
    if not group_name:
        await message.answer("❓ Группа не привязана")
        await state.clear()
        return

    day = data["add_day"]
    num = data["add_num"]
    t_start, t_end = LESSON_TIMES[num]

    new_lesson = {
        "weekday": day,
        "week_type": data["add_week_type"],
        "lesson_number": num,
        "time_start": t_start,
        "time_end": t_end,
        "subject": data["add_subject"],
        "lesson_type": data["add_lesson_type"],
        "teacher": data.get("add_teacher"),
        "room": None if room == "-" else room,
        "subgroup": None,
    }

    lessons = load_schedule(group_name)
    lessons.append(new_lesson)
    save_schedule(group_name, lessons)
    logger.info("Добавлена пара [%s]: %s, день %d", group_name, new_lesson["subject"], day)

    await state.clear()
    await state.update_data(group_name = group_name)
    await message.answer(
        f"✅ Пара добавлена:\n\n{_format_lesson(new_lesson)}",
        reply_markup = back_to_menu_kb(),
    )


# ===== EDIT FLOW =====

@router.callback_query(F.data == "ed:edt")
async def cb_edit_start(callback: CallbackQuery) -> None:
    """Изменение: выбор дня"""

    if not await _is_callback_admin(callback):
        await callback.answer("⛔ Только админ", show_alert = True)
        return

    await callback.message.edit_text(
        "✏️ Изменить пару\nВыберите день:",
        reply_markup = edit_days_kb("ed:ed:"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:ed:"))
async def cb_edit_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменение: список пар на выбранный день"""

    day = int(callback.data.split(":")[2])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)
    if not group_name:
        await callback.message.edit_text("❓ Группа не привязана")
        return

    lessons = load_schedule(group_name)
    await callback.message.edit_text(
        f"✏️ Изменить пару — {DAY_NAMES_FULL[day - 1]}\nВыберите пару:",
        reply_markup = lessons_list_kb(lessons, day, "ed:el:", "ed:edt"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:el:"))
async def cb_edit_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменение: выбор поля"""

    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)
    lessons = load_schedule(group_name)

    if idx >= len(lessons):
        await callback.answer("Пара не найдена, попробуйте снова", show_alert = True)
        return

    lesson = lessons[idx]
    await state.update_data(
        edit_idx = idx,
        edit_weekday = lesson["weekday"],
        edit_lesson_number = lesson["lesson_number"],
        edit_subject = lesson["subject"],
    )

    await callback.message.edit_text(
        f"✏️ Что изменить?\n\n{_format_lesson(lesson)}",
        reply_markup = edit_field_kb(idx, lesson["weekday"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:ef:"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменение: выбрано поле — FSM или кнопки"""

    parts = callback.data.split(":")
    idx, field = int(parts[2]), parts[3]

    if field == "typ":
        await callback.message.edit_text(
            f"Выберите новый тип занятия:",
            reply_markup = edit_lesson_type_kb(idx),
        )
    elif field == "wt":
        await callback.message.edit_text(
            f"Выберите новый тип недели:",
            reply_markup = edit_week_type_kb(idx),
        )
    elif field == "dn":
        await callback.message.edit_text(
            "Выберите новый день:",
            reply_markup = move_day_kb(idx),
        )
    else:
        field_name = FIELD_NAMES.get(field, "значение")
        await state.update_data(edit_field = field, edit_field_idx = idx)
        await state.set_state(EditSchedule.edit_value)

        if callback.message.chat.type != "private":
            await callback.message.edit_text(
                f"Введите новое значение для поля <b>{field_name}</b>\n"
                "(или <code>-</code> чтобы очистить):",
            )
            await callback.message.answer(
                "↩️ Ответьте на это сообщение:",
                reply_markup = ForceReply(selective = True),
            )
        else:
            await callback.message.edit_text(
                f"Введите новое значение для поля <b>{field_name}</b>\n"
                "(или <code>-</code> чтобы очистить):",
                reply_markup = cancel_kb(),
            )

    await callback.answer()


@router.message(EditSchedule.edit_value, F.text)
async def fsm_edit_value(message: Message, state: FSMContext) -> None:
    """FSM: ввод нового значения для текстового поля"""

    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(message.chat.id)
    idx = data["edit_field_idx"]
    field = data["edit_field"]

    lessons = load_schedule(group_name)

    expected = {
        "weekday": data.get("edit_weekday"),
        "lesson_number": data.get("edit_lesson_number"),
        "subject": data.get("edit_subject"),
    }

    if not _verify_lesson(lessons, idx, expected):
        await state.clear()
        await state.update_data(group_name = group_name)
        await message.answer(
            "⚠️ Расписание изменилось, попробуйте снова",
            reply_markup = back_to_menu_kb(),
        )
        return

    value = message.text.strip()
    if value == "-":
        value = None

    field_key = {"sub": "subject", "tch": "teacher", "rm": "room"}[field]
    old_value = lessons[idx][field_key]
    lessons[idx][field_key] = value
    save_schedule(group_name, lessons)

    field_name = FIELD_NAMES.get(field, field)
    logger.info(
        "Изменена пара [%s]: %s, %s: %s → %s",
        group_name, lessons[idx]["subject"], field_name, old_value, value,
    )

    await state.clear()
    await state.update_data(group_name = group_name)
    await message.answer(
        f"✅ {field_name} изменён: {value or '(пусто)'}",
        reply_markup = back_to_menu_kb(),
    )


# --- Edit: set lesson type ---

@router.callback_query(F.data.startswith("ed:st:"))
async def cb_set_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить тип занятия"""

    parts = callback.data.split(":")
    idx, lt = int(parts[2]), parts[3]
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)

    lessons = load_schedule(group_name)
    expected = {
        "weekday": data.get("edit_weekday"),
        "lesson_number": data.get("edit_lesson_number"),
        "subject": data.get("edit_subject"),
    }

    if not _verify_lesson(lessons, idx, expected):
        await callback.message.edit_text(
            "⚠️ Расписание изменилось, попробуйте снова",
            reply_markup = back_to_menu_kb(),
        )
        await callback.answer()
        return

    new_type = LESSON_TYPE_MAP[lt]
    lessons[idx]["lesson_type"] = new_type
    save_schedule(group_name, lessons)
    logger.info("Изменён тип [%s]: %s → %s", group_name, lessons[idx]["subject"], new_type)

    await callback.message.edit_text(
        f"✅ Тип занятия изменён: {new_type}",
        reply_markup = back_to_menu_kb(),
    )
    await callback.answer()


# --- Edit: set week type ---

@router.callback_query(F.data.startswith("ed:sw:"))
async def cb_set_week(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить тип недели"""

    parts = callback.data.split(":")
    idx, wt = int(parts[2]), parts[3]
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)

    lessons = load_schedule(group_name)
    expected = {
        "weekday": data.get("edit_weekday"),
        "lesson_number": data.get("edit_lesson_number"),
        "subject": data.get("edit_subject"),
    }

    if not _verify_lesson(lessons, idx, expected):
        await callback.message.edit_text(
            "⚠️ Расписание изменилось, попробуйте снова",
            reply_markup = back_to_menu_kb(),
        )
        await callback.answer()
        return

    new_wt = WEEK_TYPE_MAP[wt]
    lessons[idx]["week_type"] = new_wt
    save_schedule(group_name, lessons)
    logger.info("Изменён тип недели [%s]: %s → %s", group_name, lessons[idx]["subject"], new_wt)

    await callback.message.edit_text(
        f"✅ Тип недели изменён: {WEEK_TYPE_DISPLAY[new_wt]}",
        reply_markup = back_to_menu_kb(),
    )
    await callback.answer()


# --- Edit: move lesson (day + number) ---

@router.callback_query(F.data.startswith("ed:md:"))
async def cb_move_day(callback: CallbackQuery) -> None:
    """Перенос: выбор нового номера пары"""

    parts = callback.data.split(":")
    idx, day = int(parts[2]), int(parts[3])

    await callback.message.edit_text(
        f"Перенести в {DAY_NAMES_FULL[day - 1]}\nВыберите номер пары:",
        reply_markup = move_number_kb(idx, day),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ed:mn:"))
async def cb_move_number(callback: CallbackQuery, state: FSMContext) -> None:
    """Перенос: выполнить"""

    parts = callback.data.split(":")
    idx, new_day, new_num = int(parts[2]), int(parts[3]), int(parts[4])
    data = await state.get_data()
    group_name = data.get("group_name") or _get_group_name(callback.message.chat.id)

    lessons = load_schedule(group_name)
    expected = {
        "weekday": data.get("edit_weekday"),
        "lesson_number": data.get("edit_lesson_number"),
        "subject": data.get("edit_subject"),
    }

    if not _verify_lesson(lessons, idx, expected):
        await callback.message.edit_text(
            "⚠️ Расписание изменилось, попробуйте снова",
            reply_markup = back_to_menu_kb(),
        )
        await callback.answer()
        return

    t_start, t_end = LESSON_TIMES[new_num]
    lessons[idx]["weekday"] = new_day
    lessons[idx]["lesson_number"] = new_num
    lessons[idx]["time_start"] = t_start
    lessons[idx]["time_end"] = t_end
    save_schedule(group_name, lessons)

    logger.info(
        "Перенесена пара [%s]: %s → %s, %d-я пара",
        group_name, lessons[idx]["subject"], DAY_NAMES_FULL[new_day - 1], new_num,
    )

    await callback.message.edit_text(
        f"✅ Пара перенесена: {DAY_NAMES_FULL[new_day - 1]}, {new_num}-я пара ({t_start}–{t_end})",
        reply_markup = back_to_menu_kb(),
    )
    await callback.answer()
