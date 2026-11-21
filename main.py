"""
拾光账本 —— 双端适配版（全局共享分类 + 弹出式卡通键盘）
UI 优化版：修复 Flet 1.0+ 弃用警告，优化桌面端布局对齐
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import flet as ft

# ==========================================================
# 调试模式配置：
# 可选 "mobile"（模拟手机） / "desktop"（模拟电脑） / None（自动检测）
# ==========================================================
FORCE_PLATFORM = None

# ============================================================
# 兼容层
# ============================================================
Colors = getattr(ft, "Colors", None) or getattr(ft, "colors", None)
Icons = getattr(ft, "Icons", None) or getattr(ft, "icons", None)
DropdownOption = getattr(ft, "DropdownOption", None) or getattr(getattr(ft, "dropdown", None), "Option", None)
ScrollMode = getattr(ft, "ScrollMode", None)
PrimaryButton = getattr(ft, "FilledButton", None) or getattr(ft, "ElevatedButton", None) or getattr(ft, "Button", None)
CrossAxisAlignment = getattr(ft, "CrossAxisAlignment", None)
MainAxisAlignment = getattr(ft, "MainAxisAlignment", None)
FontWeight = getattr(ft, "FontWeight", None)
TextAlign = getattr(ft, "TextAlign", None)
TextOverflow = getattr(ft, "TextOverflow", None)
Offset = getattr(ft, "Offset", None)
if Offset is None:
    try:
        Offset = ft.transform.Offset
    except Exception:
        pass


def pad_sym(h: float = 0, v: float = 0):
    cls = getattr(ft, "Padding", None)
    if cls and hasattr(cls, "symmetric"):
        try:
            return cls.symmetric(horizontal=h, vertical=v)
        except:
            pass
    mod = getattr(ft, "padding", None)
    if mod and hasattr(mod, "symmetric"):
        try:
            return mod.symmetric(horizontal=h, vertical=v)
        except:
            pass
    return None


def alignment_center():
    cls = getattr(ft, "Alignment", None)
    if cls:
        try:
            return cls(0, 0)
        except:
            pass
    mod = getattr(ft, "alignment", None)
    if mod: return getattr(mod, "center", None)
    return None


def no_border():
    cls = getattr(ft, "NoInputBorder", None)
    if cls:
        try:
            return cls()
        except:
            pass
    cls2 = getattr(ft, "InputBorder", None)
    if cls2 and hasattr(cls2, "NONE"): return cls2.NONE
    return None


# ============================================================
# 键名归一化
# ============================================================
def normalize_digit(key: str):
    if not key: return None
    if len(key) == 1 and key in "0123456789": return key
    lower = key.lower().replace("_", " ")
    for prefix in ("numpad", "num "):
        if lower.startswith(prefix):
            rest = lower[len(prefix):].strip()
            if len(rest) == 1 and rest.isdigit(): return rest
    if lower.startswith("num") and len(lower) == 4 and lower[3].isdigit(): return lower[3]
    if lower.startswith("digit") and len(lower) == 6 and lower[5].isdigit(): return lower[5]
    return None


def is_decimal_key(key: str) -> bool: return key in (".", "Period", "NumpadDecimal", "Numpad Decimal", "Decimal")


def is_enter_key(key: str) -> bool: return key in ("Enter", "NumpadEnter", "Numpad Enter", "Return")


def is_backspace_key(key: str) -> bool: return key in ("Backspace", "NumpadBackspace", "Delete")


DEFAULT_CATEGORIES = ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "工资", "奖金", "理财", "其他"]
DEFAULT_BOOK = "默认账本"
CARD_HEIGHT = 76
DELETE_BTN_WIDTH = 76


# ============================================================
# 数据存储路径适配
# ============================================================
def get_data_file_path() -> Path:
    env_path = os.environ.get("LEDGER_FILE")
    if env_path:
        return Path(env_path).resolve()
    flet_storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if flet_storage:
        return (Path(flet_storage) / "data.json").resolve()
    return (Path.home() / ".my_ledger" / "data.json").resolve()


DATA_FILE = get_data_file_path()
_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def split_time(date_str: str) -> tuple[str, str]:
    if not isinstance(date_str, str): return str(date_str), ""
    for fmt in _TIME_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y年%m月%d日"), dt.strftime("%H:%M")
        except ValueError:
            continue
    return date_str, ""


# ============================================================
# 数据层
# ============================================================
def default_data() -> dict:
    return {
        "version": 4,
        "current_book": DEFAULT_BOOK,
        "categories": list(DEFAULT_CATEGORIES),
        "books": {DEFAULT_BOOK: {"records": []}},
    }


def _clean_records(raw_records) -> list[dict]:
    if not isinstance(raw_records, list): return []
    out = []
    for item in raw_records:
        if not isinstance(item, dict): continue
        try:
            amount = round(float(item.get("amount", 0)), 2)
        except:
            continue
        if amount <= 0: continue
        out.append({
            "id": str(item.get("id") or uuid.uuid4().hex),
            "amount": amount,
            "type": "收入" if item.get("type") == "收入" else "支出",
            "category": str(item.get("category") or "其他"),
            "note": str(item.get("note") or ""),
            "date": str(item.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        })
    return out


def load_data() -> dict:
    if not DATA_FILE.exists(): return default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except:
        return default_data()
    if isinstance(raw, list):
        data = default_data()
        data["books"][DEFAULT_BOOK]["records"] = _clean_records(raw)
        return data
    if not isinstance(raw, dict): return default_data()

    cats_raw = raw.get("categories")
    if isinstance(cats_raw, dict):
        cats = []
        for k in ("支出", "收入"):
            for c in cats_raw.get(k, []):
                if c not in cats: cats.append(c)
        if not cats: cats = list(DEFAULT_CATEGORIES)
    elif isinstance(cats_raw, list):
        cats = list(cats_raw)
    else:
        cats = list(DEFAULT_CATEGORIES)

    books_raw = raw.get("books")
    cleaned_books: dict[str, dict] = {}
    if isinstance(books_raw, dict):
        for name, payload in books_raw.items():
            if isinstance(payload, dict):
                cleaned_books[str(name)] = {"records": _clean_records(payload.get("records", []))}

    if not cleaned_books: cleaned_books = {DEFAULT_BOOK: {"records": []}}
    current = raw.get("current_book")
    if current not in cleaned_books: current = next(iter(cleaned_books))

    return {"version": 4, "current_book": current, "categories": cats, "books": cleaned_books}


def save_data(data: dict) -> None:
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        print(f"Save error: {e}")


def to_cents(value) -> int: return int(round(float(value) * 100))


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def summarize(records: list[dict]) -> tuple[int, int]:
    income = sum(to_cents(r["amount"]) for r in records if r["type"] == "收入")
    expense = sum(to_cents(r["amount"]) for r in records if r["type"] == "支出")
    return income, expense


def category_stats(records: list[dict]) -> list[tuple[str, int, float]]:
    totals: dict[str, int] = {}
    for r in records:
        if r["type"] != "支出": continue
        totals[r["category"]] = totals.get(r["category"], 0) + to_cents(r["amount"])
    total = sum(totals.values())
    if total <= 0: return []
    return [(cat, amt, amt / total) for cat, amt in sorted(totals.items(), key=lambda kv: -kv[1])]


# ============================================================
# UI 颜色主题
# ============================================================
BG_COLOR = "#F7F9FC"
CARD_BG = "#FFFFFF"
TEXT_MAIN = "#2D3748"
TEXT_SUB = "#A0AEC0"
THEME_COLOR = "#FF8A65"
INCOME_COLOR = "#38A169"
EXPENSE_COLOR = "#E53E3E"

C_YELLOW = "#FFF3E0"
C_CLEAR = "#E8F5E9"
C_BACK = "#FFEBEE"
C_CONFIRM = THEME_COLOR
C_SCREEN = "#FAFAFA"
C_BG = "#FFFFFF"
C_TEXT = "#4A5568"


class CuteNumPad(ft.Container):
    def __init__(self, on_confirm=None, on_change=None):
        self._on_confirm = on_confirm
        self._on_change = on_change
        self._val = "0"
        self._is_neg = False

        self.display_text = ft.Text("0", size=32, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN)
        self.neg_text = ft.Text(" ", size=24, weight=FontWeight.BOLD if FontWeight else None, color=THEME_COLOR)

        super().__init__()
        self.bgcolor = C_BG
        self.border_radius = 20
        self.padding = 16
        self.visible = False
        self.shadow = ft.BoxShadow(blur_radius=15, color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                                   offset=ft.Offset(0, -5))
        self.content = ft.Column(
            controls=[self._build_screen(), self._build_pad()],
            spacing=16,
            horizontal_alignment=CrossAxisAlignment.CENTER if CrossAxisAlignment else None,
        )

    def _build_screen(self):
        return ft.Container(
            content=ft.Row([
                ft.Text("¥", size=24, weight=FontWeight.BOLD if FontWeight else None, color=THEME_COLOR),
                self.neg_text,
                self.display_text,
            ], alignment=MainAxisAlignment.CENTER, spacing=4),
            bgcolor=C_SCREEN,
            border_radius=12,
            padding=pad_sym(h=20, v=12),
            expand=True,
            border=ft.Border.all(1, "#EDF2F7")
        )

    def _key(self, label, on_click, color=C_YELLOW, text_color=C_TEXT, width=66, height=52):
        return ft.Container(
            content=ft.Text(label, size=20, weight=FontWeight.W_600 if hasattr(FontWeight, "W_600") else None,
                            color=text_color),
            bgcolor=color,
            border_radius=12,
            width=width,
            height=height,
            alignment=alignment_center(),
            on_click=on_click,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                                offset=ft.Offset(0, 2)),
        )

    def _build_pad(self):
        def press(d):
            if self._val == "0":
                self._val = d
            elif "." in self._val and len(self._val.split(".")[1]) >= 2:
                return
            elif len(self._val.replace(".", "")) >= 9:
                return
            else:
                self._val += d
            self._render()

        def dec():
            if "." not in self._val: self._val += "."
            self._render()

        def back():
            if len(self._val) > 1:
                self._val = self._val[:-1]
            else:
                self._val = "0"
            self._render()

        def clear():
            self._val = "0"
            self._is_neg = False
            self._render()

        rows = [
            [("7", lambda e: press("7"), C_YELLOW, C_TEXT, 66), ("8", lambda e: press("8"), C_YELLOW, C_TEXT, 66),
             ("9", lambda e: press("9"), C_YELLOW, C_TEXT, 66), ("⌫", lambda e: back(), C_BACK, EXPENSE_COLOR, 66)],
            [("4", lambda e: press("4"), C_YELLOW, C_TEXT, 66), ("5", lambda e: press("5"), C_YELLOW, C_TEXT, 66),
             ("6", lambda e: press("6"), C_YELLOW, C_TEXT, 66), ("清空", lambda e: clear(), C_CLEAR, INCOME_COLOR, 66)],
            [("1", lambda e: press("1"), C_YELLOW, C_TEXT, 66), ("2", lambda e: press("2"), C_YELLOW, C_TEXT, 66),
             ("3", lambda e: press("3"), C_YELLOW, C_TEXT, 66), ("00", lambda e: press("00"), C_YELLOW, C_TEXT, 66)],
            [("0", lambda e: press("0"), C_YELLOW, C_TEXT, 140), (".", lambda e: dec(), C_YELLOW, C_TEXT, 66)],
        ]

        grid = ft.Column(spacing=10)
        for row in rows:
            controls = []
            for cell in row:
                label, fn, color, text_color, width = cell
                controls.append(self._key(label, fn, color, text_color, width=width))
            grid.controls.append(ft.Row(controls, spacing=10, alignment=MainAxisAlignment.CENTER))

        confirm = ft.Container(
            content=ft.Text("🐾 确认并保存", size=18, weight=FontWeight.BOLD if FontWeight else None, color="#FFFFFF"),
            bgcolor=C_CONFIRM,
            border_radius=12,
            height=52,
            expand=True,
            alignment=alignment_center(),
            on_click=lambda e: self._confirm(),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.3, THEME_COLOR), offset=ft.Offset(0, 4)),
        )
        grid.controls.append(ft.Row([confirm], spacing=0, alignment=MainAxisAlignment.CENTER))

        return ft.Container(content=grid, expand=True)

    def _render(self):
        self.neg_text.value = "−" if self._is_neg else " "
        self.display_text.value = self._val
        try:
            self.neg_text.update()
            self.display_text.update()
        except:
            pass
        if self._on_change: self._on_change(self.float_val())

    def _confirm(self):
        v = self.float_val()
        if v <= 0: return
        if self._on_confirm: self._on_confirm(v)

    def float_val(self):
        sign = -1 if self._is_neg else 1
        try:
            return sign * float(self._val)
        except ValueError:
            return 0.0

    def reset(self):
        self._val = "0"
        self._is_neg = False
        self._render()


# ============================================================
# UI 主逻辑
# ============================================================
def main(page: ft.Page):
    def detect_mobile() -> bool:
        if FORCE_PLATFORM == "mobile": return True
        if FORCE_PLATFORM == "desktop": return False
        try:
            p = str(page.platform).lower()
            return "android" in p or "ios" in p
        except:
            return False

    IS_MOBILE = detect_mobile()

    page.title = "拾光账本"
    page.bgcolor = BG_COLOR
    page.padding = 16
    page.scroll = ScrollMode.AUTO if ScrollMode else "auto"
    if hasattr(page, "adaptive"):
        try:
            page.adaptive = True
        except:
            pass

    if IS_MOBILE:
        try:
            if hasattr(page, "window") and page.window is not None:
                page.window.width = 390
                page.window.height = 844
            else:
                page.window_width = 390
                page.window_height = 844
        except:
            pass

    data = load_data()
    current_book = data["current_book"]

    def records() -> list[dict]:
        return data["books"][current_book]["records"]

    def content_width() -> float:
        try:
            return max(240.0, (page.width or 360) - page.padding * 2)
        except:
            return 336.0

    active_dialog = {"dlg": None, "on_confirm": None}

    def toast(msg: str) -> None:
        bar = ft.SnackBar(content=ft.Text(msg, color=ft.Colors.WHITE), bgcolor=TEXT_MAIN)
        if hasattr(page, "show_dialog"):
            try:
                page.show_dialog(bar); return
            except:
                pass
        page.snack_bar = bar
        bar.open = True
        page.update()

    def open_dialog(dlg: ft.AlertDialog, on_confirm=None) -> None:
        active_dialog["dlg"] = dlg
        active_dialog["on_confirm"] = on_confirm
        if hasattr(page, "open"):
            try:
                page.open(dlg); return
            except:
                pass
        if hasattr(page, "show_dialog"):
            try:
                page.show_dialog(dlg); return
            except:
                pass
        page.dialog = dlg
        dlg.open = True
        page.update()

    def close_dialog(dlg: ft.AlertDialog = None) -> None:
        active_dialog["dlg"] = None
        active_dialog["on_confirm"] = None
        target_dlg = dlg or page.dialog or (page.overlay[-1] if page.overlay else None)
        if target_dlg:
            if hasattr(page, "close"):
                try:
                    page.close(target_dlg); return
                except:
                    pass
            if hasattr(page, "pop_dialog"):
                try:
                    page.pop_dialog(); return
                except:
                    pass
            target_dlg.open = False
            page.update()
            try:
                if target_dlg in page.overlay:
                    page.overlay.remove(target_dlg)
                    page.update()
            except:
                pass
        else:
            page.update()

    # ============================================================
    # 🌟 修复弃用警告：使用现代 InputBorder 替代 border_radius 等
    # ============================================================
    input_border = ft.OutlineInputBorder(
        border_radius=10,
        side=ft.BorderSide(width=1, color="#E2E8F0")  # ✅ 使用 side 参数
    )

    input_style = {
        "dense": True,
        "filled": True,
        "fill_color": "#F7FAFC",
        "text_size": 14,
    }
    if input_border:
        input_style["border"] = input_border

    # 修复顶部下拉框宽度问题
    book_dropdown = ft.Dropdown(
        value=current_book,
        options=[DropdownOption(b, b) for b in data["books"]],
        label="当前账本",
        width=180,  # 限制宽度
        **input_style
    )
    type_input = ft.Dropdown(
        label="类型",
        options=[DropdownOption("支出", "支出"), DropdownOption("收入", "收入")],
        value="支出",
        width=100,
        **input_style
    )

    category_input = ft.Dropdown(
        label="分类",
        options=[DropdownOption(c, c) for c in data["categories"]],
        value=data["categories"][0] if data["categories"] else "其他",
        expand=2,  # 控制比例
        **input_style
    )

    note_input = ft.TextField(label="备注", max_length=50, expand=3, **input_style)

    focus_state = {"where": None}

    def _note_focus(e):
        focus_state["where"] = "note"

    def _note_blur(e):
        focus_state["where"] = None if focus_state["where"] == "note" else focus_state["where"]

    note_input.on_focus = _note_focus
    note_input.on_blur = _note_blur

    amount_buf = {"text": ""}
    amount_field = None

    amount_display_text = ft.Text("0.00", size=28, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN)
    amount_display_control = ft.Container(
        content=ft.Row([
            ft.Text("¥", size=20, color=THEME_COLOR, weight=FontWeight.BOLD if FontWeight else None),
            amount_display_text
        ], alignment=MainAxisAlignment.START, vertical_alignment=CrossAxisAlignment.CENTER, spacing=8),
        expand=True,
        height=60,
        padding=pad_sym(h=16, v=0),
        border_radius=12,
        bgcolor="#FFFFFF",
        border=ft.Border.all(2, "#EDF2F7"),
    )

    if not IS_MOBILE:
        field_kwargs: dict = dict(value="", hint_text="0.00", text_size=20, dense=True)
        if TextAlign is not None: field_kwargs["text_align"] = TextAlign.CENTER
        cp = pad_sym(v=10)
        if cp is not None: field_kwargs["content_padding"] = cp

        # 🌟 修复金额输入框被挤压：加入 expand=True
        amount_field = ft.TextField(**field_kwargs, expand=True, border=ft.InputBorder.NONE)
        amount_field.on_submit = lambda e: add_record(e)

        amount_control = ft.Container(
            content=ft.Row([
                ft.Text("¥", size=20, color=THEME_COLOR, weight=FontWeight.BOLD if FontWeight else None),
                amount_field
            ], vertical_alignment=CrossAxisAlignment.CENTER, spacing=4),
            width=160,  # 恢复固定宽度
            padding=pad_sym(h=10, v=0),
            border_radius=10,
            bgcolor="#F7FAFC",
            border=ft.Border.all(1, "#E2E8F0")
        )

        def _amt_focus(e):
            focus_state["where"] = "amount"

        def _amt_blur(e):
            focus_state["where"] = None if focus_state["where"] == "amount" else focus_state["where"]

        amount_field.on_focus = _amt_focus
        amount_field.on_blur = _amt_blur

        def get_amount_str() -> str:
            return (amount_field.value or "").strip()

        def set_amount_str(v: str) -> None:
            amount_field.value = v
            try:
                amount_field.update()
            except:
                page.update()

    def pad_changed(v: float):
        amount_display_text.value = f"{v:.2f}" if v > 0 else "0.00"
        try:
            amount_display_text.update()
        except:
            pass

    def handle_pad_confirm(v: float):
        amount_buf["text"] = str(v)
        add_record()

    cute_pad = CuteNumPad(on_confirm=handle_pad_confirm, on_change=pad_changed)

    def show_keypad(e):
        cute_pad.visible = True
        page.update()
        try:
            cute_pad.scroll_into_view()
        except:
            pass

    amount_display_control.on_click = show_keypad

    summary_row = ft.Row(alignment=MainAxisAlignment.SPACE_BETWEEN, spacing=12)
    record_list = ft.Column(spacing=12)
    stats_column = ft.Column(spacing=16)

    def make_swipeable_record(record: dict) -> ft.Control:
        rid = record["id"]
        is_income = record["type"] == "收入"
        color = INCOME_COLOR if is_income else EXPENSE_COLOR
        sign = "+" if is_income else "-"
        card_w = content_width()
        max_ratio = -DELETE_BTN_WIDTH / card_w if card_w > 0 else -0.2

        delete_bg = ft.Container(
            content=ft.Icon(Icons.DELETE, color=ft.Colors.WHITE, size=24),
            width=DELETE_BTN_WIDTH, height=CARD_HEIGHT, right=0, top=0,
            alignment=alignment_center(), bgcolor=EXPENSE_COLOR, border_radius=14,
            on_click=lambda e: confirm_delete(rid),
        )

        date_upper, date_lower = split_time(record["date"])
        info_line = f"{date_lower} · {record['category']} · {record['note'] or '无备注'}" if date_lower else f"{record['category']} · {record['note'] or '无备注'}"

        card_row = ft.Row([
            ft.Column([
                ft.Text(date_upper, size=12, color=TEXT_SUB,
                        weight=FontWeight.W_500 if hasattr(FontWeight, "W_500") else None),
                ft.Text(info_line, size=14, color=TEXT_MAIN, max_lines=1,
                        overflow=TextOverflow.ELLIPSIS if TextOverflow else None),
            ], expand=True, spacing=4),
            ft.Text(f"{sign}¥{record['amount']:.2f}", size=18, weight=FontWeight.BOLD if FontWeight else None,
                    color=color),
        ], alignment=MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=CrossAxisAlignment.CENTER)

        card = ft.Container(
            content=card_row, padding=pad_sym(h=16, v=12),
            width=card_w, height=CARD_HEIGHT, bgcolor=CARD_BG,
            border_radius=14, offset=Offset(0, 0) if Offset else None,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                                offset=ft.Offset(0, 2)),
        )

        swipe_state = {"open": False}

        def apply_offset(open_flag: bool, animated: bool = True) -> None:
            swipe_state["open"] = open_flag
            if Offset is not None: card.offset = Offset(max_ratio if open_flag else 0, 0)
            if animated:
                try:
                    card.animate_offset = ft.Animation(200, ft.AnimationCurve.EASE_OUT)
                except:
                    pass
            try:
                card.update()
            except:
                page.update()

        def toggle_open(e=None):
            apply_offset(not swipe_state["open"])

        card.on_click = toggle_open

        def on_h_update(e) -> None:
            if Offset is None: return
            pd = getattr(e, "primary_delta", None)
            if pd is None:
                delta = getattr(e, "local_delta_x", 0) or 0
            elif hasattr(pd, "x"):
                delta = pd.x
            else:
                try:
                    delta = float(pd)
                except:
                    delta = 0.0
            current = card.offset.x if card.offset else 0.0
            new_x = max(max_ratio, min(0.0, current + delta / card_w))
            card.offset = Offset(new_x, 0)
            try:
                card.update()
            except:
                pass

        def on_h_end(e) -> None:
            current = card.offset.x if card.offset else 0.0
            apply_offset(current < max_ratio / 2)

        if hasattr(card, "on_horizontal_drag_update"):
            try:
                card.on_horizontal_drag_start = lambda e: setattr(card, 'animate_offset', None)
                card.on_horizontal_drag_update = on_h_update
                card.on_horizontal_drag_end = on_h_end
                wrapper = card
            except:
                wrapper = card
        else:
            try:
                gesture = ft.GestureDetector(content=card)
                if hasattr(gesture, "on_horizontal_drag_update"):
                    gesture.on_horizontal_drag_start = lambda e: setattr(card, 'animate_offset', None)
                    gesture.on_horizontal_drag_update = on_h_update
                    gesture.on_horizontal_drag_end = on_h_end
                    wrapper = gesture
                else:
                    wrapper = card
            except:
                wrapper = card

        return ft.Stack([delete_bg, wrapper], width=card_w, height=CARD_HEIGHT)

    def refresh_list() -> None:
        record_list.controls.clear()
        if not records():
            record_list.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(getattr(Icons, "RECEIPT_LONG", getattr(Icons, "ARTICLE", None)), size=60, color="#CBD5E0"),
                    ft.Text("还没有记账记录哦~", color=TEXT_SUB, size=14),
                ], horizontal_alignment=CrossAxisAlignment.CENTER, spacing=12),
                alignment=alignment_center(), padding=40,
            ))
            return
        for r in reversed(records()):
            record_list.controls.append(make_swipeable_record(r))

    def update_summary() -> None:
        income, expense = summarize(records())
        balance = income - expense
        balance_color = INCOME_COLOR if balance >= 0 else EXPENSE_COLOR

        def make_card(title, amount_str, color, icon_name):
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon_name, size=16, color=color),
                        ft.Text(title, size=13, color=TEXT_SUB,
                                weight=FontWeight.W_500 if hasattr(FontWeight, "W_500") else None),
                    ], spacing=6, alignment=MainAxisAlignment.CENTER),
                    ft.Text(amount_str, size=18, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN),
                ], spacing=6, horizontal_alignment=CrossAxisAlignment.CENTER),
                padding=pad_sym(h=12, v=16),
                bgcolor=CARD_BG,
                border_radius=16,
                expand=True,
                alignment=alignment_center(),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                                    offset=ft.Offset(0, 4)),
            )

        summary_row.controls = [
            make_card("总收入", f"¥{format_cents(income)}", INCOME_COLOR,
                      Icons.ARROW_DOWNWARD if hasattr(Icons, "ARROW_DOWNWARD") else Icons.ADD),
            make_card("总支出", f"¥{format_cents(expense)}", EXPENSE_COLOR,
                      Icons.ARROW_UPWARD if hasattr(Icons, "ARROW_UPWARD") else Icons.REMOVE),
            make_card("结余", f"¥{format_cents(balance)}", THEME_COLOR, Icons.ACCOUNT_BALANCE_WALLET if hasattr(Icons,
                                                                                                                "ACCOUNT_BALANCE_WALLET") else Icons.ACCOUNT_BALANCE),
        ]

    def update_stats() -> None:
        stats_column.controls.clear()
        rows = category_stats(records())
        if not rows:
            stats_column.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(getattr(Icons, "PIE_CHART_OUTLINE", getattr(Icons, "PIE_CHART", None)), size=60,
                            color="#CBD5E0"),
                    ft.Text("暂无支出数据", color=TEXT_SUB, size=14),
                ], horizontal_alignment=CrossAxisAlignment.CENTER, spacing=12),
                alignment=alignment_center(), padding=40,
            ))
            return
        for cat, cents, pct in rows:
            stats_column.controls.append(ft.Column([
                ft.Row([
                    ft.Text(cat, size=14, weight=FontWeight.W_600 if hasattr(FontWeight, "W_600") else None,
                            color=TEXT_MAIN),
                    ft.Text(f"¥{format_cents(cents)} ({pct * 100:.1f}%)", size=13, color=TEXT_SUB),
                ], alignment=MainAxisAlignment.SPACE_BETWEEN),
                ft.ProgressBar(value=pct, height=8, color=THEME_COLOR, bgcolor="#EDF2F7", border_radius=4),
            ], spacing=6))

    def refresh_all() -> None:
        refresh_list()
        update_summary()
        update_stats()
        for ctl in (record_list, summary_row, stats_column):
            try:
                ctl.update()
            except:
                pass
        page.update()

    last_add = {"t": 0.0}

    def add_record(e=None) -> None:
        now = time.time()
        if now - last_add["t"] < 0.25: return
        last_add["t"] = now

        if IS_MOBILE:
            raw = amount_buf["text"].strip()
        else:
            raw = get_amount_str().rstrip(".")

        if not raw:
            toast("请输入金额")
            return
        try:
            amount = round(float(raw), 2)
        except:
            toast("金额格式不正确")
            return
        if amount <= 0:
            toast("金额必须大于 0")
            return

        kind = type_input.value or "支出"
        cat = category_input.value or "其他"

        records().append({
            "id": uuid.uuid4().hex, "amount": amount, "type": kind, "category": cat,
            "note": (note_input.value or "").strip(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        save_data(data)

        if IS_MOBILE:
            cute_pad.reset()
            amount_buf["text"] = ""
            amount_display_text.value = "0.00"
            try:
                amount_display_text.update()
            except:
                pass
            cute_pad.visible = False
            try:
                cute_pad.update()
            except:
                pass
        else:
            set_amount_str("")
            # 🌟 修复 Warning：使用 page.run_task 调用异步 focus
            try:
                page.run_task(amount_field.focus)
            except:
                pass

        refresh_all()
        toast("✅ 记账成功")

    def confirm_delete(rec_id: str) -> None:
        target = next((r for r in records() if r["id"] == rec_id), None)
        if not target: return
        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("删除记录？", color=TEXT_MAIN),
            content=ft.Text(
                f"{target['date']}\n{target['type']} · {target['category']} · ¥{target['amount']:.2f}\n{target['note'] or '无备注'}",
                size=14, color=TEXT_SUB),
            actions=[
                ft.TextButton(content=ft.Text("取消", color=TEXT_SUB), on_click=lambda e: close_dialog(dlg)),
                ft.TextButton(content=ft.Text("删除", color=EXPENSE_COLOR),
                              on_click=lambda e: do_delete_record(dlg, rec_id)),
            ],
        )
        open_dialog(dlg, on_confirm=lambda e=None: do_delete_record(dlg, rec_id))

    def do_delete_record(dlg: ft.AlertDialog, rec_id: str) -> None:
        records()[:] = [r for r in records() if r["id"] != rec_id]
        save_data(data)
        close_dialog(dlg)
        refresh_all()
        toast("已删除")

    def on_type_change(e) -> None:
        page.update()

    type_input.on_change = on_type_change

    def on_book_change(e) -> None:
        nonlocal current_book
        new_book = book_dropdown.value
        if not new_book or new_book not in data["books"]:
            book_dropdown.value = current_book
            try:
                book_dropdown.update()
            except:
                pass
            return
        if new_book == current_book: return
        current_book = new_book
        data["current_book"] = new_book
        save_data(data)
        if IS_MOBILE:
            cute_pad.reset()
            amount_buf["text"] = ""
            amount_display_text.value = "0.00"
            try:
                amount_display_text.update()
            except:
                pass
            cute_pad.visible = False
            try:
                cute_pad.update()
            except:
                pass
        else:
            set_amount_str("")
        note_input.value = ""
        refresh_all()

    book_dropdown.on_change = on_book_change

    def refresh_book_dropdown() -> None:
        book_dropdown.on_change = None
        book_dropdown.options = [DropdownOption(b, b) for b in data["books"]]
        book_dropdown.value = current_book
        try:
            book_dropdown.update()
        except:
            pass
        book_dropdown.on_change = on_book_change

    def open_new_book_dialog(e=None) -> None:
        name_input = ft.TextField(label="账本名称", dense=True, autofocus=True, **input_style)

        def create(e=None):
            nonlocal current_book
            name = name_input.value.strip()
            if not name or name in data["books"]:
                toast("账本名称无效或已存在")
                return
            data["books"][name] = {"records": []}
            data["current_book"] = name
            current_book = name
            save_data(data)
            close_dialog(dlg)
            refresh_book_dropdown()
            refresh_all()
            toast(f"已创建账本「{name}」")

        dlg = ft.AlertDialog(
            title=ft.Text("新建账本", color=TEXT_MAIN), content=name_input,
            actions=[
                ft.TextButton(content=ft.Text("取消", color=TEXT_SUB), on_click=lambda e: close_dialog(dlg)),
                ft.TextButton(content=ft.Text("创建", color=THEME_COLOR), on_click=create),
            ],
        )
        open_dialog(dlg, on_confirm=create)

    def open_rename_book_dialog(e=None) -> None:
        old_name = current_book
        name_input = ft.TextField(label="账本新名称", value=old_name, dense=True, autofocus=True, **input_style)

        def do_rename(e=None):
            nonlocal current_book
            new_name = name_input.value.strip()
            if not new_name: toast("名称不能为空"); return
            if new_name == old_name: close_dialog(dlg); return
            if new_name in data["books"]: toast("该名称已存在"); return
            data["books"][new_name] = data["books"].pop(old_name)
            data["current_book"] = new_name
            current_book = new_name
            save_data(data)
            close_dialog(dlg)
            refresh_book_dropdown()
            refresh_all()
            toast(f"已重命名为「{new_name}」")

        dlg = ft.AlertDialog(
            title=ft.Text("重命名账本", color=TEXT_MAIN), content=name_input,
            actions=[
                ft.TextButton(content=ft.Text("取消", color=TEXT_SUB), on_click=lambda e: close_dialog(dlg)),
                ft.TextButton(content=ft.Text("确定", color=THEME_COLOR), on_click=do_rename),
            ],
        )
        open_dialog(dlg, on_confirm=do_rename)

    def open_delete_book_dialog(e=None) -> None:
        if len(data["books"]) <= 1: toast("至少保留一个账本"); return
        target = current_book

        def do_delete(dlg):
            nonlocal current_book
            if target not in data["books"]: close_dialog(dlg); return
            data["books"].pop(target)
            if current_book == target:
                current_book = next(iter(data["books"]))
                data["current_book"] = current_book
            save_data(data)
            close_dialog(dlg)
            refresh_book_dropdown()
            refresh_all()
            toast(f"已删除账本「{target}」")

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("删除账本？", color=TEXT_MAIN),
            content=ft.Text(f"将删除「{target}」及其下 {len(records())} 条记录，此操作不可撤销。", size=14, color=TEXT_SUB),
            actions=[
                ft.TextButton(content=ft.Text("取消", color=TEXT_SUB), on_click=lambda e: close_dialog(dlg)),
                ft.TextButton(content=ft.Text("删除", color=EXPENSE_COLOR), on_click=lambda e: do_delete(dlg)),
            ],
        )
        open_dialog(dlg, on_confirm=lambda e=None: do_delete(dlg))

    def open_category_manager(e=None) -> None:
        cats = data["categories"]
        items = ft.Column(spacing=10)

        def refresh_items():
            items.controls.clear()
            for c in cats:
                text_label = ft.Text(c, expand=True, size=15, color=TEXT_MAIN)
                name_field = ft.TextField(value=c, dense=True, expand=True, visible=False, **input_style)
                btn_edit = ft.IconButton(icon=Icons.EDIT, icon_size=18, icon_color=TEXT_SUB)
                btn_save = ft.IconButton(icon=Icons.CHECK, icon_size=18, icon_color=INCOME_COLOR, visible=False)

                def make_start_edit(cat_name, lbl, fld, b_edit, b_save):
                    def start(e):
                        lbl.visible = False;
                        fld.visible = True
                        b_edit.visible = False;
                        b_save.visible = True
                        try:
                            fld.focus()
                        except:
                            pass
                        page.update()

                    return start

                def make_save_edit(cat_name, lbl, fld, b_edit, b_save):
                    def save(e):
                        new_name = fld.value.strip()
                        if new_name and new_name != cat_name:
                            if new_name in cats: toast("该分类已存在"); return
                            idx = cats.index(cat_name)
                            cats[idx] = new_name
                            for b in data["books"].values():
                                for r in b["records"]:
                                    if r["category"] == cat_name: r["category"] = new_name
                            save_data(data)
                            if category_input.value == cat_name: category_input.value = new_name
                            category_input.options = [DropdownOption(c, c) for c in cats]
                        lbl.value = new_name or cat_name
                        lbl.visible = True;
                        fld.visible = False
                        b_edit.visible = True;
                        b_save.visible = False
                        refresh_all()

                    return save

                btn_edit.on_click = make_start_edit(c, text_label, name_field, btn_edit, btn_save)
                btn_save.on_click = make_save_edit(c, text_label, name_field, btn_edit, btn_save)
                btn_del = ft.IconButton(icon=Icons.DELETE, icon_size=18, icon_color=EXPENSE_COLOR,
                                        on_click=lambda e, cat=c: remove_category(cat))

                items.controls.append(ft.Row([text_label, name_field, btn_edit, btn_save, btn_del],
                                             alignment=MainAxisAlignment.SPACE_BETWEEN))
            try:
                items.update()
            except:
                pass

        def remove_category(cat: str):
            if cat in cats:
                cats.remove(cat)
                if not cats: cats.append("其他")
                save_data(data)
                category_input.options = [DropdownOption(c, c) for c in cats]
                if category_input.value not in cats: category_input.value = cats[0]
                refresh_items()
                refresh_all()

        def add_category(e=None):
            name = new_cat_input.value.strip()
            if not name or name in cats: toast("分类名无效或已存在"); return
            cats.append(name)
            new_cat_input.value = ""
            save_data(data)
            category_input.options = [DropdownOption(c, c) for c in cats]
            category_input.value = name
            refresh_items()
            refresh_all()

        new_cat_input = ft.TextField(label="新分类名称", expand=True, **input_style)
        dlg = ft.AlertDialog(
            title=ft.Text("管理全局分类", color=TEXT_MAIN),
            content=ft.Column([
                ft.Text("修改会同步到所有账本和记录", size=12, color=TEXT_SUB),
                items,
                ft.Row([
                    new_cat_input,
                    ft.IconButton(icon=Icons.ADD, on_click=add_category, icon_color=THEME_COLOR, bgcolor="#FFF3E0")
                ]),
            ], spacing=16, tight=True, scroll=ScrollMode.AUTO if ScrollMode else None),
            actions=[ft.TextButton(content=ft.Text("关闭", color=TEXT_SUB), on_click=lambda e: close_dialog(dlg))],
        )
        refresh_items()
        open_dialog(dlg)

    btn_manage_cat = ft.IconButton(
        icon=Icons.EDIT, tooltip="管理全局分类", icon_size=20, icon_color=TEXT_SUB,
        on_click=open_category_manager,
    )

    if not IS_MOBILE:
        def on_keyboard(e) -> None:
            key = getattr(e, "key", None)
            if not key: return
            dlg = active_dialog.get("dlg")
            if dlg:
                if is_enter_key(key):
                    cb = active_dialog.get("on_confirm")
                    if cb:
                        cb(None)
                    else:
                        close_dialog(dlg)
                    return
                if key in ("Escape", "Esc"): close_dialog(dlg); return

            if focus_state["where"] == "note": return
            if key in ("Delete", "Del"):
                if records(): confirm_delete(records()[-1]["id"])
                return
            if is_enter_key(key):
                if get_amount_str(): add_record()
                return
            if focus_state["where"] == "amount": return

            digit = normalize_digit(key)
            if digit is not None:
                try:
                    page.run_task(amount_field.focus)
                except:
                    pass
                current = amount_field.value or ""
                if "." in current:
                    if len(current.split(".", 1)[1]) >= 2: return
                else:
                    if len(current) >= 12: return
                amount_field.value = current + digit
                try:
                    amount_field.update()
                except:
                    page.update()
                return

            if is_decimal_key(key):
                try:
                    page.run_task(amount_field.focus)
                except:
                    pass
                current = amount_field.value or ""
                if "." in current: return
                if not current: current = "0"
                amount_field.value = current + "."
                try:
                    amount_field.update()
                except:
                    page.update()
                return

        try:
            page.on_keyboard_event = on_keyboard
        except:
            pass

    # ============================================================
    # 布局排版
    # ============================================================

    # 修复顶部工具栏：限制下拉框宽度
    book_toolbar = ft.Container(
        content=ft.Row([
            ft.Icon(Icons.BOOK if hasattr(Icons, "BOOK") else Icons.BOOKMARK, size=20, color=THEME_COLOR),
            book_dropdown,
            ft.IconButton(icon=Icons.ADD, tooltip="新建账本", on_click=open_new_book_dialog, icon_size=20,
                          icon_color=TEXT_SUB),
            ft.IconButton(icon=getattr(Icons, "DRIVE_FILE_RENAME_OUTLINE", None) or Icons.EDIT,
                          tooltip="重命名当前账本", on_click=open_rename_book_dialog, icon_size=20,
                          icon_color=TEXT_SUB),
            ft.IconButton(icon=getattr(Icons, "DELETE_OUTLINE", None) or Icons.DELETE, tooltip="删除当前账本",
                          icon_color=EXPENSE_COLOR, on_click=open_delete_book_dialog, icon_size=20),
        ], alignment=MainAxisAlignment.START, vertical_alignment=CrossAxisAlignment.CENTER, spacing=8),
        padding=pad_sym(h=12, v=8),
        bgcolor=CARD_BG,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 2))
    )

    if IS_MOBILE:
        form_block = ft.Column([
            ft.Row([type_input, category_input, btn_manage_cat], spacing=12,
                   vertical_alignment=CrossAxisAlignment.CENTER),
            amount_display_control,
            note_input,
            ft.Container(height=10),
            cute_pad,
        ], spacing=16)
        save_btn = None
    else:
        # 调整桌面端比例，防止输入框被挤压
        form_block = ft.Row([
            type_input,
            category_input,
            btn_manage_cat,
            amount_control,
            note_input,
        ], spacing=12, vertical_alignment=CrossAxisAlignment.CENTER)

        save_btn = PrimaryButton(
            content=ft.Text("保 存", size=16, weight=FontWeight.BOLD if FontWeight else None),
            icon=Icons.SAVE if hasattr(Icons, "SAVE") else None,
            on_click=add_record,
            width=120,
            height=48,
            style=ft.ButtonStyle(
                bgcolor=THEME_COLOR,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=2,
            ) if hasattr(ft, "ButtonStyle") else None
        )

    form_container = ft.Container(
        content=form_block,
        padding=20,
        bgcolor=CARD_BG,
        border_radius=16,
        shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 4))
    )

    page.add(
        ft.SafeArea(
            ft.Column([
                summary_row,
                ft.Container(height=8),
                book_toolbar,
                ft.Container(height=8),
                ft.Text("记一笔", size=18, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN),
                form_container,
                ft.Container(content=save_btn, alignment=alignment_center(),
                             padding=ft.Margin(0, 8, 0, 8)) if save_btn else ft.Container(),
                ft.Container(height=16),
                ft.Text("流水记录", size=18, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN),
                record_list,
                ft.Container(height=16),
                ft.Text("分类统计（支出）", size=18, weight=FontWeight.BOLD if FontWeight else None, color=TEXT_MAIN),
                ft.Container(
                    content=stats_column,
                    padding=16,
                    bgcolor=CARD_BG,
                    border_radius=16,
                    shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                                        offset=ft.Offset(0, 4))
                ),
                ft.Container(height=40),
            ], spacing=12, scroll=ScrollMode.AUTO if ScrollMode else None),
            expand=True,
        )
    )

    refresh_all()


if __name__ == "__main__":
    ft.run(main)
