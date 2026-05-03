from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# ─── FOYDALANUVCHI MENU ──────────────────────────────────────

def user_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🔗 Linkimni olish"),
        KeyboardButton(text="👥 Achkolarim")
    )
    kb.row(
        KeyboardButton(text="🎁 Bal berish"),
        KeyboardButton(text="📞 Admin bilan bog'lanish")
    )
    return kb.as_markup(resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🚀 Give Away boshlash"),
        KeyboardButton(text="⛔ Tugatish")
    )
    kb.row(
        KeyboardButton(text="📢 Reklama"),
        KeyboardButton(text="📈 Admin statistika")
    )
    kb.row(
        KeyboardButton(text="📡 Hammaga yuborish")
    )
    kb.row(
        KeyboardButton(text="🏆 G'oliblar"),
        KeyboardButton(text="💾 Backup olish")
    )
    kb.row(
        KeyboardButton(text="🚫 Ban"),
        KeyboardButton(text="✉️ Foydalanuvchiga yozish")
    )
    kb.row(
        KeyboardButton(text="⚖️ Bal boshqaruv")
    )
    kb.row(
        KeyboardButton(text="🔗 Linkimni olish")
    )
    kb.row(
        KeyboardButton(text="👥 Achkolarim"),
        KeyboardButton(text="📞 Admin bilan bog'lanish")
    )
    return kb.as_markup(resize_keyboard=True)


# ─── A'ZOLIK TEKSHIRUV ───────────────────────────────────────

def join_keyboard(group_url: str, channel_url: str = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Guruhga qo'shilish", url=group_url)
    if channel_url:
        kb.button(text="📢 Kanalga qo'shilish", url=channel_url)
    kb.button(text="✅ Tekshirish", callback_data="check_membership")
    kb.adjust(1)
    return kb.as_markup()


# ─── TASDIQLASH ──────────────────────────────────────────────

def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"confirm:{action}")
    kb.button(text="❌ Bekor qilish", callback_data="cancel")
    kb.adjust(2)
    return kb.as_markup()


def end_giveaway_confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⛔ Ha, tugatish", callback_data="confirm:end_giveaway")
    kb.button(text="❌ Yo'q, davom etsin", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


# ─── SAHIFALASH ──────────────────────────────────────────────

def pagination_keyboard(current: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if current > 1:
        kb.button(text="⬅️", callback_data=f"{prefix}:{current - 1}")
    kb.button(text=f"{current}/{total_pages}", callback_data="noop")
    if current < total_pages:
        kb.button(text="➡️", callback_data=f"{prefix}:{current + 1}")
    kb.adjust(3)
    return kb.as_markup()


# ─── TRANSFER ────────────────────────────────────────────────

def transfer_confirm(to_name: str, count: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"✅ Ha, {count} ta ball beraman",
        callback_data="confirm:transfer"
    )
    kb.button(text="❌ Bekor", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


# ─── G'OLIBLAR ───────────────────────────────────────────────

def winner_contact_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Yozish", url=f"tg://user?id={user_id}")
    kb.adjust(1)
    return kb.as_markup()