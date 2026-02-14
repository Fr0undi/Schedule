"""Обработчик загрузки PDF-файлов с расписанием от администратора"""

from pathlib import Path

from aiogram import Router, F


from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import settings

from bot.logger import get_logger

from bot.services.pdf_parser import parse_pdf_all_groups
from bot.services.storage import save_schedule, load_groups, load_university

from bot.keyboards.upload_kb import (
    upload_forms_kb,
    upload_institutes_kb,
    upload_levels_kb,
    upload_courses_kb,
)


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
async def handle_pdf_upload(message: Message, state: FSMContext) -> None:
    is_global_admin = message.from_user.id in settings.ADMIN_IDS
    admin_groups = [] if is_global_admin else await _get_admin_groups(message)

    if not is_global_admin and not admin_groups:
        await message.answer("⛔ У вас нет прав для загрузки расписания")
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        await message.answer("📄 Отправьте файл в формате PDF")
        return

    # Сохранить PDF на диск
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents = True, exist_ok = True)
    file_path = data_dir / doc.file_name

    try:
        file = await message.bot.download(doc.file_id, destination = str(file_path))
        if file:
            file.close()
        logger.info("PDF скачан: %s", file_path)
    except Exception:
        logger.exception("Ошибка загрузки PDF")
        await message.answer("❌ Ошибка при загрузке файла")
        return

    if is_global_admin:
        # Глобальный админ: выбор иерархии перед парсингом
        await state.update_data(pdf_path = str(file_path))
        uni = load_university()
        forms = uni.get("forms", [])

        if not forms:
            # Нет структуры — парсить сразу (обратная совместимость)
            status_msg = await message.answer("⏳ Обрабатываю PDF...")
            await _process_pdf_global(status_msg, str(file_path))
            return

        await message.answer(
            "📄 PDF получен\n\nВыберите форму обучения:",
            reply_markup = upload_forms_kb(forms),
        )
    else:
        # Админ чата: парсить сразу, обновлять только свои группы
        status_msg = await message.answer("⏳ Обрабатываю PDF...")
        await _process_pdf_chat_admin(status_msg, str(file_path), admin_groups)


async def _process_pdf_global(
    status_msg: Message,
    file_path: str,
    form: str | None = None,
    institute: str | None = None,
    level: str | None = None,
    course: int | None = None,
) -> None:
    """Парсинг PDF для глобального админа (все группы)"""

    try:
        all_groups = parse_pdf_all_groups(file_path)

        if not all_groups:
            await status_msg.edit_text(
                "❌ Не удалось разобрать PDF\n"
                "Группы не найдены или таблица пуста\n"
                "Подробности в логах"
            )
            return

        for group_name, lessons in all_groups.items():
            save_schedule(group_name, lessons, form = form, institute = institute, level = level, course = course)

        group_list = "\n".join(
            f"  • {name}: {len(lessons)} пар"
            for name, lessons in all_groups.items()
        )

        await status_msg.edit_text(
            f"✅ Расписание обновлено!\n"
            f"Обновлено групп: {len(all_groups)}\n\n"
            f"{group_list}"
        )
        logger.info("Расписание обновлено для %d групп", len(all_groups))

    except Exception:
        logger.exception("Ошибка при обработке PDF")
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке PDF. Подробности в логах"
        )


async def _process_pdf_chat_admin(status_msg: Message, file_path: str, admin_groups: list[str]) -> None:
    """Парсинг PDF для админа чата (только его группы, метаданные сохраняются)"""

    try:
        all_groups = parse_pdf_all_groups(file_path)

        if not all_groups:
            await status_msg.edit_text(
                "❌ Не удалось разобрать PDF\n"
                "Группы не найдены или таблица пуста\n"
                "Подробности в логах"
            )
            return

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


# --- Callback-цепочка выбора иерархии (глобальный админ) ---

@router.callback_query(F.data == "up:forms")
async def cb_upload_forms(callback: CallbackQuery) -> None:
    """Показать выбор формы обучения"""

    uni = load_university()
    forms = uni.get("forms", [])

    await callback.message.edit_text(
        "📄 Выберите форму обучения:",
        reply_markup = upload_forms_kb(forms),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("up:f:"))
async def cb_upload_form(callback: CallbackQuery) -> None:
    """Форма выбрана → показать институты"""

    form_code = callback.data.split(":")[2]
    uni = load_university()
    form = next((f for f in uni.get("forms", []) if f["code"] == form_code), None)

    if not form:
        await callback.answer("Форма не найдена", show_alert = True)
        return

    await callback.message.edit_text(
        "🏛 Выберите институт:",
        reply_markup = upload_institutes_kb(form["institutes"], form_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("up:i:"))
async def cb_upload_institute(callback: CallbackQuery) -> None:
    """Институт выбран → показать уровни"""

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
        reply_markup = upload_levels_kb(inst["levels"], form_code, inst_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("up:l:"))
async def cb_upload_level(callback: CallbackQuery) -> None:
    """Уровень выбран → показать курсы"""

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
        reply_markup = upload_courses_kb(level["courses"], form_code, inst_code, level_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("up:c:"))
async def cb_upload_course(callback: CallbackQuery, state: FSMContext) -> None:
    """Курс выбран → парсить PDF с метаданными"""

    parts = callback.data.split(":")
    form_code = parts[2]
    inst_code = parts[3]
    level_code = parts[4]
    course = int(parts[5])

    data = await state.get_data()
    pdf_path = data.get("pdf_path")

    if not pdf_path:
        await callback.message.edit_text("❌ PDF файл не найден, отправьте заново")
        await callback.answer()
        return

    # Переместить PDF в директорию группы: schedules/form/inst/course/
    old_path = Path(pdf_path)
    new_name = f"{form_code}_{inst_code}_{level_code}_{course}.pdf"
    dest_dir = Path(settings.DATA_DIR) / "schedules" / form_code / inst_code / str(course)
    dest_dir.mkdir(parents = True, exist_ok = True)
    new_path = dest_dir / new_name
    try:
        old_path.replace(new_path)
        pdf_path = str(new_path)
        logger.info("PDF перемещён: %s", new_path)
    except Exception:
        logger.warning("Не удалось переместить PDF, используем исходный путь")

    await callback.message.edit_text("⏳ Обрабатываю PDF...")
    await callback.answer()

    await _process_pdf_global(
        callback.message,
        pdf_path,
        form = form_code,
        institute = inst_code,
        level = level_code,
        course = course,
    )
    await state.clear()
