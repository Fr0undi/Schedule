"""Reply-клавиатура с основными командами"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для личных чатов (красивые кнопки)"""

    return ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text = "📅 Сегодня"), KeyboardButton(text = "📅 Завтра")],
            [KeyboardButton(text = "📆 Неделя"), KeyboardButton(text = "✏️ Редактировать")],
            [KeyboardButton(text = "📋 Привязка"), KeyboardButton(text = "❓ Помощь")],
        ],
        resize_keyboard = True,
    )


def group_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для групповых чатов (команды, работают с privacy mode)"""

    return ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text = "/today"), KeyboardButton(text = "/tomorrow")],
            [KeyboardButton(text = "/week"), KeyboardButton(text = "/edit")],
            [KeyboardButton(text = "/register"), KeyboardButton(text = "/help")],
        ],
        resize_keyboard = True,
    )
