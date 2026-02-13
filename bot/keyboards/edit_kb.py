"""Inline-клавиатуры для редактирования расписания"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


DAY_NAMES_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

WEEK_TYPE_LABELS = {"both": "об.", "odd": "нечет.", "even": "чет."}

LESSON_TIMES = {
    1: ("09:00", "10:35"),
    2: ("10:55", "12:30"),
    3: ("13:00", "14:35"),
    4: ("14:55", "16:30"),
    5: ("16:50", "18:25"),
    6: ("18:30", "20:05"),
    7: ("20:15", "21:50"),
}


def edit_main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню: удалить / добавить / изменить"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "🗑 Удалить пару", callback_data = "ed:del")],
        [InlineKeyboardButton(text = "➕ Добавить пару", callback_data = "ed:add")],
        [InlineKeyboardButton(text = "✏️ Изменить пару", callback_data = "ed:edt")],
    ])


def edit_days_kb(prefix: str, back_cb: str = "ed:menu") -> InlineKeyboardMarkup:
    """Выбор дня недели (Пн-Сб)"""

    buttons = []
    row = []
    for i, name in enumerate(DAY_NAMES_SHORT, start = 1):
        row.append(InlineKeyboardButton(text = name, callback_data = f"{prefix}{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = back_cb)])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def lessons_list_kb(all_lessons: list[dict], day: int, cb_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    """Список пар на день с кнопками"""

    buttons = []
    for idx, lesson in enumerate(all_lessons):
        if lesson["weekday"] != day:
            continue
        wt = WEEK_TYPE_LABELS.get(lesson["week_type"], "")
        num = lesson["lesson_number"]
        subj = lesson["subject"]
        if len(subj) > 25:
            subj = subj[:23] + ".."
        label = f"{num}. {lesson['time_start']} {subj} ({wt})"
        buttons.append([InlineKeyboardButton(text = label, callback_data = f"{cb_prefix}{idx}")])

    if not buttons:
        buttons.append([InlineKeyboardButton(text = "Пар нет", callback_data = back_cb)])

    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = back_cb)])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def delete_confirm_kb(idx: int, day: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления пары"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "Да, удалить", callback_data = f"ed:dc:{idx}")],
        [InlineKeyboardButton(text = "« Отмена", callback_data = f"ed:d:{day}")],
    ])


def add_lesson_number_kb(day: int) -> InlineKeyboardMarkup:
    """Выбор номера пары 1-7"""

    buttons = []
    row = []
    for num in range(1, 8):
        t_start, t_end = LESSON_TIMES[num]
        row.append(InlineKeyboardButton(
            text = f"{num}. {t_start}",
            callback_data = f"ed:an:{day}:{num}",
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "ed:add")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def add_week_type_kb(day: int, num: int) -> InlineKeyboardMarkup:
    """Выбор типа недели"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [
            InlineKeyboardButton(text = "Обе", callback_data = f"ed:aw:{day}:{num}:b"),
            InlineKeyboardButton(text = "Чётная", callback_data = f"ed:aw:{day}:{num}:e"),
            InlineKeyboardButton(text = "Нечётная", callback_data = f"ed:aw:{day}:{num}:o"),
        ],
        [InlineKeyboardButton(text = "« Назад", callback_data = f"ed:ad:{day}")],
    ])


def add_lesson_type_kb(day: int, num: int, wt: str) -> InlineKeyboardMarkup:
    """Выбор типа занятия"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [
            InlineKeyboardButton(text = "Лекция", callback_data = f"ed:at:{day}:{num}:{wt}:lk"),
            InlineKeyboardButton(text = "Практика", callback_data = f"ed:at:{day}:{num}:{wt}:pr"),
        ],
        [
            InlineKeyboardButton(text = "Лабораторная", callback_data = f"ed:at:{day}:{num}:{wt}:lb"),
            InlineKeyboardButton(text = "Другое", callback_data = f"ed:at:{day}:{num}:{wt}:dr"),
        ],
        [InlineKeyboardButton(text = "« Отмена", callback_data = "ed:cancel")],
    ])


def edit_field_kb(idx: int, day: int) -> InlineKeyboardMarkup:
    """Выбор поля для изменения"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [
            InlineKeyboardButton(text = "Предмет", callback_data = f"ed:ef:{idx}:sub"),
            InlineKeyboardButton(text = "Тип занятия", callback_data = f"ed:ef:{idx}:typ"),
        ],
        [
            InlineKeyboardButton(text = "Преподаватель", callback_data = f"ed:ef:{idx}:tch"),
            InlineKeyboardButton(text = "Аудитория", callback_data = f"ed:ef:{idx}:rm"),
        ],
        [
            InlineKeyboardButton(text = "Тип недели", callback_data = f"ed:ef:{idx}:wt"),
            InlineKeyboardButton(text = "День/номер", callback_data = f"ed:ef:{idx}:dn"),
        ],
        [InlineKeyboardButton(text = "« Назад", callback_data = f"ed:ed:{day}")],
    ])


def edit_lesson_type_kb(idx: int) -> InlineKeyboardMarkup:
    """Выбор нового типа занятия"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [
            InlineKeyboardButton(text = "Лекция", callback_data = f"ed:st:{idx}:lk"),
            InlineKeyboardButton(text = "Практика", callback_data = f"ed:st:{idx}:pr"),
        ],
        [
            InlineKeyboardButton(text = "Лабораторная", callback_data = f"ed:st:{idx}:lb"),
            InlineKeyboardButton(text = "Другое", callback_data = f"ed:st:{idx}:dr"),
        ],
    ])


def edit_week_type_kb(idx: int) -> InlineKeyboardMarkup:
    """Выбор нового типа недели"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [
            InlineKeyboardButton(text = "Обе", callback_data = f"ed:sw:{idx}:b"),
            InlineKeyboardButton(text = "Чётная", callback_data = f"ed:sw:{idx}:e"),
            InlineKeyboardButton(text = "Нечётная", callback_data = f"ed:sw:{idx}:o"),
        ],
    ])


def move_day_kb(idx: int) -> InlineKeyboardMarkup:
    """Выбор нового дня для переноса"""

    buttons = []
    row = []
    for i, name in enumerate(DAY_NAMES_SHORT, start = 1):
        row.append(InlineKeyboardButton(text = name, callback_data = f"ed:md:{idx}:{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def move_number_kb(idx: int, day: int) -> InlineKeyboardMarkup:
    """Выбор нового номера пары для переноса"""

    buttons = []
    row = []
    for num in range(1, 8):
        t_start, _ = LESSON_TIMES[num]
        row.append(InlineKeyboardButton(
            text = f"{num}. {t_start}",
            callback_data = f"ed:mn:{idx}:{day}:{num}",
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM-шагов"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "« Отмена", callback_data = "ed:cancel")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню после завершения"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "« В меню", callback_data = "ed:menu")],
    ])
