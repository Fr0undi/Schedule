"""Reply-клавиатура с основными командами (только для личных чатов)"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# Текст кнопки → имя команды-обработчика
BUTTON_COMMANDS: dict[str, str] = {
    "📅 Сегодня": "today",
    "📅 Завтра": "tomorrow",
    "📆 Неделя": "week",
    "✏️ Редакт.": "edit",
    "📋 Привязка": "register",
    "❓ Помощь": "help",
}

BUTTON_TEXTS = set(BUTTON_COMMANDS.keys())


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text = "📅 Сегодня"), KeyboardButton(text = "📅 Завтра")],
            [KeyboardButton(text = "📆 Неделя"), KeyboardButton(text = "✏️ Редакт.")],
            [KeyboardButton(text = "📋 Привязка"), KeyboardButton(text = "❓ Помощь")],
        ],
        resize_keyboard = True,
    )
