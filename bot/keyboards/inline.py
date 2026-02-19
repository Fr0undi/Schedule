"""Инлайн-клавиатуры с кнопкой WebApp и URL-ссылкой"""

from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def webapp_keyboard(base_url: str, week_type: str, group_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}?week={week_type}&group={quote(group_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            web_app = WebAppInfo(url = url),
        )
    ]])


def url_keyboard(base_url: str, week_type: str, group_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}?week={week_type}&group={quote(group_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            url = url,
        )
    ]])


def teacher_webapp_keyboard(base_url: str, week_type: str, teacher_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}/teachers?week={week_type}&name={quote(teacher_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            web_app = WebAppInfo(url = url),
        )
    ]])


def teacher_url_keyboard(base_url: str, week_type: str, teacher_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}/teachers?week={week_type}&name={quote(teacher_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            url = url,
        )
    ]])


