import json
import os
from datetime import datetime

from config import DATA_DIR, SUPPLY_DIAMETERS, PACKAGE_SIZES, CUPCAKE_BOX_SIZES, LOW_STOCK_THRESHOLDS

# ─── Категории для отображения ────────────────────────────────────────────────
CATEGORY_NAMES = {
    "substrates":   "Подложка",
    "boxes":        "Коробка",
    "packages":     "Пакет",
    "cupcake_boxes": "Коробка капкейк/трайфл",
}


def _get_path(user_id: int) -> str:
    return os.path.join(DATA_DIR, f"{user_id}.json")


def _default_data() -> dict:
    return {
        "stock": {
            "substrates":   {str(d): 0 for d in SUPPLY_DIAMETERS},
            "boxes":        {str(d): 0 for d in SUPPLY_DIAMETERS},
            "packages":     {s: 0 for s in PACKAGE_SIZES},
            "cupcake_boxes": {s: 0 for s in CUPCAKE_BOX_SIZES},
        },
        "history": [],
    }


def load(user_id: int) -> dict:
    path = _get_path(user_id)
    if not os.path.exists(path):
        return _default_data()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(user_id: int, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _get_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


# ─── Приход ───────────────────────────────────────────────────────────────────

def add_income(user_id: int, category: str, size: str, qty: int) -> None:
    """
    Добавить qty единиц расходника в категорию category (substrates / boxes / packages).
    """
    data = load(user_id)
    stock = data["stock"][category]
    stock[size] = stock.get(size, 0) + qty
    data["history"].append({
        "date":     _now(),
        "type":     "income",
        "category": category,
        "size":     size,
        "qty":      qty,
    })
    _save(user_id, data)


# ─── Расход (торт) ────────────────────────────────────────────────────────────

def add_expense_cake(user_id: int, diameter: int, package_size: str) -> dict:
    """
    Списать 1 подложку диаметра diameter, 1 коробку диаметра diameter,
    1 пакет размера package_size.

    Возвращает:
        {"ok": True}                           — успех
        {"ok": False, "shortages": [...]}      — не хватает позиций
    """
    data = load(user_id)
    stock = data["stock"]
    d = str(diameter)

    shortages: list[str] = []
    if stock["substrates"].get(d, 0) < 1:
        shortages.append(f"подложка {diameter}см")
    if stock["boxes"].get(d, 0) < 1:
        shortages.append(f"коробка {diameter}см")
    if stock["packages"].get(package_size, 0) < 1:
        shortages.append(f"пакет {package_size}")

    if shortages:
        return {"ok": False, "shortages": shortages}

    stock["substrates"][d] -= 1
    stock["boxes"][d]      -= 1
    stock["packages"][package_size] -= 1

    data["history"].append({
        "date":          _now(),
        "type":          "expense",
        "cake_diameter": diameter,
        "items": [
            {"category": "substrates", "size": d,            "qty": 1},
            {"category": "boxes",      "size": d,            "qty": 1},
            {"category": "packages",   "size": package_size, "qty": 1},
        ],
    })
    _save(user_id, data)
    return {"ok": True}


# ─── Расход (капкейки/трайфлы) ───────────────────────────────────────────────────

def add_expense_cupcake(user_id: int, box_size: str) -> dict:
    """
    Списать 1 коробку для капкейков/трайфлов соответствующего размера.
    """
    data = load(user_id)
    stock = data["stock"]["cupcake_boxes"]
    available = stock.get(box_size, 0)

    if available < 1:
        return {"ok": False, "shortages": [f"коробка {box_size}"]}

    stock[box_size] -= 1
    data["history"].append({
        "date":     _now(),
        "type":     "expense_cupcake",
        "box_size": box_size,
    })
    _save(user_id, data)
    return {"ok": True}


# ─── Ручное удаление ─────────────────────────────────────────────────────────

def remove_manual(user_id: int, category: str, size: str, qty: int) -> dict:
    """
    Вручную убрать qty единиц из категории category.
    Возвращает {"ok": True} или {"ok": False, "available": N}.
    """
    data = load(user_id)
    stock = data["stock"][category]
    available = stock.get(size, 0)

    if available < qty:
        return {"ok": False, "available": available}

    stock[size] -= qty
    data["history"].append({
        "date":     _now(),
        "type":     "remove",
        "category": category,
        "size":     size,
        "qty":      qty,
    })
    _save(user_id, data)
    return {"ok": True}


# ─── Текст остатков ───────────────────────────────────────────────────────────

def get_stock_text(user_id: int) -> str:
    stock = load(user_id)["stock"]
    lines = ["📦 <b>Текущие остатки:</b>\n"]

    lines.append("<b>Подложки:</b>")
    for size, qty in stock["substrates"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size}см — {qty} шт {mark}".rstrip())

    lines.append("\n<b>Коробки:</b>")
    for size, qty in stock["boxes"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size}см — {qty} шт {mark}".rstrip())

    lines.append("\n<b>Пакеты:</b>")
    for size, qty in stock["packages"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size} — {qty} шт {mark}".rstrip())

    return "\n".join(lines)


# ─── Текст истории ────────────────────────────────────────────────────────────

def get_history_text(user_id: int, limit: int = 20) -> str:
    history = load(user_id)["history"]
    if not history:
        return "История пуста."

    recent = history[-limit:]
    lines = [f"📋 <b>История (последние {len(recent)} операций):</b>\n"]

    for entry in reversed(recent):
        date = entry["date"]
        if entry["type"] == "income":
            cat  = CATEGORY_NAMES.get(entry["category"], entry["category"])
            size = entry["size"]
            qty  = entry["qty"]
            unit = "см" if entry["category"] != "packages" else ""
            lines.append(f"➕ <b>{date}</b>\n    Приход: {cat} {size}{unit} × {qty} шт")
        elif entry["type"] == "expense":
            d = entry["cake_diameter"]
            lines.append(f"➖ <b>{date}</b>\n    Расход: торт {d}см")
            for item in entry["items"]:
                cat  = CATEGORY_NAMES.get(item["category"], item["category"])
                unit = "см" if item["category"] != "packages" else ""
                lines.append(f"        · {cat} {item['size']}{unit}")
        elif entry["type"] == "expense_cupcake":
            lines.append(f"➖ <b>{date}</b>\n    Расход: капкейки/трайфлы\n        · Коробка {entry['box_size']}")
        elif entry["type"] == "remove":
            cat  = CATEGORY_NAMES.get(entry["category"], entry["category"])
            size = entry["size"]
            qty  = entry["qty"]
            unit = "см" if entry["category"] != "packages" else ""
            lines.append(f"🗑 <b>{date}</b>\n    Удаление: {cat} {size}{unit} × {qty} шт")
        lines.append("")

    return "\n".join(lines).strip()


# ─── Проверка низких остатков ──────────────────────────────────────────────────────

def get_low_stock_warnings(user_id: int) -> list[str]:
    """Возвращает список позиций, у которых остаток ниже порога."""
    stock = load(user_id)["stock"]
    warnings: list[str] = []
    for category, threshold in LOW_STOCK_THRESHOLDS.items():
        cat_stock = stock.get(category, {})
        for size, qty in cat_stock.items():
            if qty < threshold:
                label = CATEGORY_NAMES.get(category, category)
                unit  = "см" if category not in ("packages", "cupcake_boxes") else ""
                warnings.append(f"{label} {size}{unit} — {qty} шт (мин. {threshold})")
    return warnings


def get_all_user_ids() -> list[int]:
    """Возвращает ID всех пользователей, у которых есть данные."""
    if not os.path.exists(DATA_DIR):
        return []
    ids = []
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json"):
            try:
                ids.append(int(fname[:-5]))
            except ValueError:
                pass
    return ids
