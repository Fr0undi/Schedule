"""FastAPI-приложение для отображения расписания в WebApp"""

from datetime import date

from fastapi import FastAPI, Request, Query

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.config import settings

from bot.services.storage import get_full_schedule
from bot.services.week_utils import get_week_type, get_week_type_display, get_week_number
from bot.services.formatter import _lesson_word

app = FastAPI(title = "Schedule WebApp")
app.mount("/static", StaticFiles(directory = "webapp/static"), name = "static")
templates = Jinja2Templates(directory = "webapp/templates")
templates.env.filters["lesson_word"] = _lesson_word

DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

TYPE_EMOJI = {
    "Лекция": "📘",
    "Практика": "📕",
    "Лабораторная": "📗",
}


@app.get("/")
async def schedule_page(
    request: Request,
    week: str = Query(default = None),
):
    today = date.today()
    current_week_type = get_week_type(today, settings.SEMESTER_START)
    week_type = week if week in ("odd", "even") else current_week_type
    week_num = get_week_number(today, settings.SEMESTER_START)

    odd_schedule = get_full_schedule("odd")
    even_schedule = get_full_schedule("even")

    # Определяем какой день раскрыть
    weekday = today.weekday()
    active_schedule = odd_schedule if week_type == "odd" else even_schedule
    if weekday == 6 or (weekday == 5 and 5 not in active_schedule):
        weekday = 0  # Воскресенье или суббота без пар → понедельник

    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "group_name": settings.GROUP_NAME,
        "week_type": week_type,
        "week_num": week_num,
        "odd_display": "Нечётная (числитель)",
        "even_display": "Чётная (знаменатель)",
        "today_weekday": weekday,
        "day_names": DAY_NAMES,
        "odd_schedule": odd_schedule,
        "even_schedule": even_schedule,
        "type_emoji": TYPE_EMOJI,
    })
