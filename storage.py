import json
import os
from datetime import datetime

from config import SHARED_STOCK_FILE, SUPPLY_DIAMETERS, PACKAGE_SIZES, CUPCAKE_BOX_SIZES, LOW_STOCK_THRESHOLDS

# ─── Категории для отображения ────────────────────────────────────────────────
CATEGORY_NAMES = {
    "substrates":   "Подложка",
    "boxes":        "Коробка",
    "packages":     "Пакет",
    "cupcake_boxes": "Коробка капкейк/трайфл",
}


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


def load() -> dict:
    if not os.path.exists(SHARED_STOCK_FILE):
        return _default_data()
    with open(SHARED_STOCK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    stock = data.setdefault("stock", {})

    # Подложки и коробки (торт) — синхронизация диаметров из конфига
    for cat in ("substrates", "boxes"):
        cat_stock = stock.setdefault(cat, {})
        expected  = {str(d) for d in SUPPLY_DIAMETERS}
        for d in expected:
            cat_stock.setdefault(d, 0)
        for d in [k for k in cat_stock if k not in expected]:
            del cat_stock[d]

    # Пакеты
    pkg = stock.setdefault("packages", {})
    for s in PACKAGE_SIZES:
        pkg.setdefault(s, 0)
    for s in [k for k in pkg if k not in PACKAGE_SIZES]:
        del pkg[s]

    # Коробки капкейк/трайфл
    cpk = stock.setdefault("cupcake_boxes", {})
    for s in CUPCAKE_BOX_SIZES:
        cpk.setdefault(s, 0)
    for s in [k for k in cpk if k not in CUPCAKE_BOX_SIZES]:
        del cpk[s]

    data.setdefault("history", [])
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(SHARED_STOCK_FILE), exist_ok=True)
    with open(SHARED_STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


# ─── Приход ───────────────────────────────────────────────────────────────────

def add_income(user_id: int, category: str, size: str, qty: int, by_name: str = "") -> None:
    data = load()
    stock = data["stock"][category]
    stock[size] = stock.get(size, 0) + qty
    data["history"].append({
        "date":     _now(),
        "by":       by_name,
        "type":     "income",
        "category": category,
        "size":     size,
        "qty":      qty,
    })
    _save(data)


# ─── Расход (торт) ────────────────────────────────────────────────────────────

def add_expense_cake(user_id: int, diameter: int, package_size: str, by_name: str = "") -> dict:
    data = load()
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
        "by":            by_name,
        "type":          "expense",
        "cake_diameter": diameter,
        "items": [
            {"category": "substrates", "size": d,            "qty": 1},
            {"category": "boxes",      "size": d,            "qty": 1},
            {"category": "packages",   "size": package_size, "qty": 1},
        ],
    })
    _save(data)
    return {"ok": True}


# ─── Расход (капкейки/трайфлы) ───────────────────────────────────────────────

def add_expense_cupcake(user_id: int, box_size: str, by_name: str = "") -> dict:
    data = load()
    stock = data["stock"]["cupcake_boxes"]
    available = stock.get(box_size, 0)

    if available < 1:
        return {"ok": False, "shortages": [f"коробка {box_size}"]}

    stock[box_size] -= 1
    data["history"].append({
        "date":     _now(),
        "by":       by_name,
        "type":     "expense_cupcake",
        "box_size": box_size,
    })
    _save(data)
    return {"ok": True}


# ─── Ручное удаление ─────────────────────────────────────────────────────────

def remove_manual(user_id: int, category: str, size: str, qty: int, by_name: str = "") -> dict:
    data = load()
    stock = data["stock"][category]
    available = stock.get(size, 0)

    if available < qty:
        return {"ok": False, "available": available}

    stock[size] -= qty
    data["history"].append({
        "date":     _now(),
        "by":       by_name,
        "type":     "remove",
        "category": category,
        "size":     size,
        "qty":      qty,
    })
    _save(data)
    return {"ok": True}


# ─── Текст остатков ───────────────────────────────────────────────────────────

def get_stock_text(user_id: int = 0) -> str:
    stock = load()["stock"]
    lines = ["📦 <b>Текущие остатки:</b>\n"]

    lines.append("<b>Подложки:</b>")
    for size, qty in stock["substrates"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size}см — {qty} шт {mark}".rstrip())

    lines.append("\n<b>Коробки (торт):</b>")
    for size, qty in stock["boxes"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size}см — {qty} шт {mark}".rstrip())

    lines.append("\n<b>Пакеты:</b>")
    for size, qty in stock["packages"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size} — {qty} шт {mark}".rstrip())

    lines.append("\n<b>Коробки капкейк/трайфл:</b>")
    for size, qty in stock["cupcake_boxes"].items():
        mark = "⚠️" if qty == 0 else ""
        lines.append(f"  • {size} — {qty} шт {mark}".rstrip())

    return "\n".join(lines)


# ─── Текст истории ────────────────────────────────────────────────────────────

def get_history_text(user_id: int = 0, limit: int = 20) -> str:
    history = load()["history"]
    if not history:
        return "История пуста."

    recent = history[-limit:]
    lines = [f"📋 <b>История (последние {len(recent)} операций):</b>\n"]

    for entry in reversed(recent):
        date = entry["date"]
        who  = f" [{entry['by']}]" if entry.get("by") else ""
        if entry["type"] == "income":
            cat  = CATEGORY_NAMES.get(entry["category"], entry["category"])
            size = entry["size"]
            qty  = entry["qty"]
            unit = "см" if entry["category"] not in ("packages", "cupcake_boxes") else ""
            lines.append(f"➕ <b>{date}</b>{who}\n    Приход: {cat} {size}{unit} × {qty} шт")
        elif entry["type"] == "expense":
            d = entry["cake_diameter"]
            lines.append(f"➖ <b>{date}</b>{who}\n    Расход: торт {d}см")
            for item in entry["items"]:
                cat  = CATEGORY_NAMES.get(item["category"], item["category"])
                unit = "см" if item["category"] not in ("packages", "cupcake_boxes") else ""
                lines.append(f"        · {cat} {item['size']}{unit}")
        elif entry["type"] == "expense_cupcake":
            lines.append(f"➖ <b>{date}</b>{who}\n    Расход: капкейки/трайфлы\n        · Коробка {entry['box_size']}")
        elif entry["type"] == "remove":
            cat  = CATEGORY_NAMES.get(entry["category"], entry["category"])
            size = entry["size"]
            qty  = entry["qty"]
            unit = "см" if entry["category"] not in ("packages", "cupcake_boxes") else ""
            lines.append(f"🗑 <b>{date}</b>{who}\n    Удаление: {cat} {size}{unit} × {qty} шт")
        lines.append("")

    return "\n".join(lines).strip()


# ─── Проверка низких остатков ─────────────────────────────────────────────────

def get_low_stock_warnings(user_id: int = 0) -> list[str]:
    stock = load()["stock"]
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
    """Возвращает ID всех пользователей из ALLOWED_USERS (для ежедневных уведомлений)."""
    from config import ALLOWED_USERS
    return list(ALLOWED_USERS)

