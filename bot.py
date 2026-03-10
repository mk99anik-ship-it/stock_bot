import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import storage
from config import (
    BOT_TOKEN,
    GREETINGS,
    HISTORY_LIMIT,
    PACKAGE_MAPPING,
    PACKAGE_SIZES,
    SUPPLY_DIAMETERS,
    VALID_CAKE_DIAMETERS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=MemoryStorage())


# ════════════════════════════════════════════════════════════════════════════════
# FSM States
# ════════════════════════════════════════════════════════════════════════════════

class IncomeStates(StatesGroup):
    choose_category = State()
    choose_size     = State()
    enter_qty       = State()

class ExpenseStates(StatesGroup):
    enter_diameter = State()

class RemoveStates(StatesGroup):
    choose_category = State()
    choose_size     = State()
    enter_qty       = State()


# ════════════════════════════════════════════════════════════════════════════════
# Keyboards
# ════════════════════════════════════════════════════════════════════════════════

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Приход",        callback_data="income")],
        [InlineKeyboardButton(text="➖ Расход (торт)", callback_data="expense")],
        [InlineKeyboardButton(text="� Удалить вручную",  callback_data="remove")],
        [InlineKeyboardButton(text="�📦 Остатки",       callback_data="stock")],
        [InlineKeyboardButton(text="📋 История",       callback_data="history")],
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")],
    ])


def kb_income_category() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟦 Подложки",  callback_data="cat:substrates")],
        [InlineKeyboardButton(text="📦 Коробки",   callback_data="cat:boxes")],
        [InlineKeyboardButton(text="🛍 Пакеты",    callback_data="cat:packages")],
        [InlineKeyboardButton(text="◀️ Назад",     callback_data="back_main")],
    ])

def kb_remove_category() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔷 Подложки",  callback_data="rmcat:substrates")],
        [InlineKeyboardButton(text="📦 Коробки",   callback_data="rmcat:boxes")],
        [InlineKeyboardButton(text="🛍 Пакеты",    callback_data="rmcat:packages")],
        [InlineKeyboardButton(text="◀️ Назад",     callback_data="back_main")],
    ])


def kb_remove_size(category: str) -> InlineKeyboardMarkup:
    if category == "packages":
        rows = [
            [InlineKeyboardButton(text=s, callback_data=f"rmsize:{s}")]
            for s in PACKAGE_SIZES
        ]
    else:
        rows = [
            [InlineKeyboardButton(text=f"{d} см", callback_data=f"rmsize:{d}")]
            for d in SUPPLY_DIAMETERS
        ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_remove_category")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_size(category: str) -> InlineKeyboardMarkup:
    if category == "packages":
        rows = [
            [InlineKeyboardButton(text=s, callback_data=f"size:{s}")]
            for s in PACKAGE_SIZES
        ]
    else:
        rows = [
            [InlineKeyboardButton(text=f"{d} см", callback_data=f"size:{d}")]
            for d in SUPPLY_DIAMETERS
        ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_category")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════════

CATEGORY_LABELS = {
    "substrates": "подложки",
    "boxes":      "коробки",
    "packages":   "пакета",
}

CATEGORY_LABELS_TITLE = {
    "substrates": "Подложки",
    "boxes":      "Коробки",
    "packages":   "Пакеты",
}


async def _edit_or_send(obj: CallbackQuery | Message, text: str,
                        markup: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение (для CallbackQuery) или отправляет новое (для Message)."""
    if isinstance(obj, CallbackQuery):
        await obj.message.edit_text(text, reply_markup=markup)
    else:
        await obj.answer(text, reply_markup=markup)


# ════════════════════════════════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════════════════════════════════

# Счётчик приветствий на пользователя: {user_id: индекс}
_greet_counter: dict[int, int] = {}


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    uid  = message.from_user.id
    name = message.from_user.first_name or "друг"
    idx  = _greet_counter.get(uid, 0) % len(GREETINGS)
    _greet_counter[uid] = idx + 1
    greeting = GREETINGS[idx].format(name=name)
    await message.answer(
        f"{greeting}\n\nВыберите действие:",
        reply_markup=kb_main(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Навигация назад
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Выберите действие:", reply_markup=kb_main())


@dp.callback_query(F.data == "back_category")
async def cb_back_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(IncomeStates.choose_category)
    await callback.message.edit_text(
        "Выберите категорию расходника:",
        reply_markup=kb_income_category(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Остатки
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "stock")
async def cb_stock(callback: CallbackQuery) -> None:
    text = storage.get_stock_text(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb_back_main())


# ════════════════════════════════════════════════════════════════════════════════
# История
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "history")
async def cb_history(callback: CallbackQuery) -> None:
    text = storage.get_history_text(callback.from_user.id, limit=HISTORY_LIMIT)
    await callback.message.edit_text(text, reply_markup=kb_back_main())


# ════════════════════════════════════════════════════════════════════════════════
# Приход — шаг 1: выбор категории
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "income")
async def cb_income_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(IncomeStates.choose_category)
    await callback.message.edit_text(
        "Выберите категорию расходника:",
        reply_markup=kb_income_category(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Приход — шаг 2: выбор размера
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(IncomeStates.choose_category, F.data.startswith("cat:"))
async def cb_income_choose_size(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(IncomeStates.choose_size)
    label = CATEGORY_LABELS.get(category, category)
    await callback.message.edit_text(
        f"Выберите размер {label}:",
        reply_markup=kb_size(category),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Приход — шаг 3: ввод количества
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(IncomeStates.choose_size, F.data.startswith("size:"))
async def cb_income_enter_qty(callback: CallbackQuery, state: FSMContext) -> None:
    size = callback.data.split(":", 1)[1]
    await state.update_data(size=size)
    await state.set_state(IncomeStates.enter_qty)
    await callback.message.edit_text(f"Введите количество для размера <b>{size}</b>:")


@dp.message(IncomeStates.enter_qty)
async def msg_income_save(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ Введите целое положительное число:")
        return

    qty = int(raw)
    data     = await state.get_data()
    category = data["category"]
    size     = data["size"]

    storage.add_income(message.from_user.id, category, size, qty)
    await state.clear()

    label = CATEGORY_LABELS_TITLE.get(category, category)
    unit  = "см" if category != "packages" else ""
    await message.answer(
        f"✅ <b>Приход записан</b>\n{label} {size}{unit} — +{qty} шт",
        reply_markup=kb_main(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Расход — шаг 1: запрос диаметра
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "expense")
async def cb_expense_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ExpenseStates.enter_diameter)
    valid = ", ".join(str(d) for d in VALID_CAKE_DIAMETERS)
    await callback.message.edit_text(
        f"Введите диаметр торта (в см):\n<i>Допустимые значения: {valid}</i>"
    )


# ════════════════════════════════════════════════════════════════════════════════
# Расход — шаг 2: обработка диаметра
# ════════════════════════════════════════════════════════════════════════════════

@dp.message(ExpenseStates.enter_diameter)
async def msg_expense_process(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""

    if not raw.isdigit():
        await message.answer("⚠️ Введите число (диаметр в см):")
        return

    diameter = int(raw)

    # ── Проверка на нестандартный диаметр ────────────────────────────────────
    if diameter not in VALID_CAKE_DIAMETERS:
        valid = ", ".join(str(d) for d in VALID_CAKE_DIAMETERS)
        await message.answer(
            f"⚠️ <b>Нестандартный диаметр: {diameter} см</b>\n\n"
            f"Диаметр 20 см не используется. "
            f"Допустимые значения: {valid}\n\n"
            f"Введите корректный диаметр:"
        )
        return  # Остаёмся в том же состоянии — ждём повторного ввода

    # ── Поиск подходящего пакета ──────────────────────────────────────────────
    package_size = PACKAGE_MAPPING.get(diameter)
    if not package_size:
        # Диаметр допустим, но пакет не задан в конфиге — сообщаем и выходим
        await state.clear()
        await message.answer(
            f"⚠️ Для диаметра {diameter}см не задан пакет.\n"
            f"Обновите <code>PACKAGE_MAPPING</code> в <code>config.py</code>.",
            reply_markup=kb_main(),
        )
        return

    # ── Списание ──────────────────────────────────────────────────────────────
    result = storage.add_expense_cake(message.from_user.id, diameter, package_size)
    await state.clear()

    if not result["ok"]:
        shortages = "\n".join(f"  · {s}" for s in result["shortages"])
        await message.answer(
            f"❌ <b>Недостаточно на складе:</b>\n{shortages}",
            reply_markup=kb_main(),
        )
        return

    await message.answer(
        f"✅ <b>Расход записан — торт {diameter}см</b>\n\n"
        f"Списано:\n"
        f"  · Подложка {diameter}см — 1 шт\n"
        f"  · Коробка  {diameter}см — 1 шт\n"
        f"  · Пакет {package_size}   — 1 шт",
        reply_markup=kb_main(),
    )


@dp.callback_query(F.data == "back_remove_category")
async def cb_back_remove_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(RemoveStates.choose_category)
    await callback.message.edit_text(
        "Выберите категорию для удаления:",
        reply_markup=kb_remove_category(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Удаление вручную — шаг 1: выбор категории
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "remove")
async def cb_remove_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(RemoveStates.choose_category)
    await callback.message.edit_text(
        "Выберите категорию для удаления:",
        reply_markup=kb_remove_category(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Удаление вручную — шаг 2: выбор размера
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(RemoveStates.choose_category, F.data.startswith("rmcat:"))
async def cb_remove_choose_size(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(RemoveStates.choose_size)
    label = CATEGORY_LABELS.get(category, category)
    await callback.message.edit_text(
        f"Выберите размер {label}:",
        reply_markup=kb_remove_size(category),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Удаление вручную — шаг 3: ввод количества
# ════════════════════════════════════════════════════════════════════════════════

@dp.callback_query(RemoveStates.choose_size, F.data.startswith("rmsize:"))
async def cb_remove_enter_qty(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    size = callback.data.split(":", 1)[1]
    await state.update_data(size=size)
    await state.set_state(RemoveStates.enter_qty)
    await callback.message.edit_text(
        f"Введите количество для удаления (<b>{size}</b>):"
    )


@dp.message(RemoveStates.enter_qty)
async def msg_remove_save(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ Введите целое положительное число:")
        return

    qty  = int(raw)
    data = await state.get_data()
    category = data["category"]
    size     = data["size"]

    result = storage.remove_manual(message.from_user.id, category, size, qty)
    await state.clear()

    if not result["ok"]:
        available = result["available"]
        await message.answer(
            f"❌ Недостаточно на складе.\n"
            f"Запрошено: {qty} шт, доступно: {available} шт.",
            reply_markup=kb_main(),
        )
        return

    label = CATEGORY_LABELS_TITLE.get(category, category)
    unit  = "см" if category != "packages" else ""
    await message.answer(
        f"🗑 <b>Удалено</b>\n{label} {size}{unit} — −{qty} шт",
        reply_markup=kb_main(),
    )


# ════════════════════════════════════════════════════════════════════════════════
# Запуск
# ════════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Проверьте файл .env")
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
