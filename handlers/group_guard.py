import logging
import re
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command

import database as db
from config import (
    GROUP_ID, ADMIN_IDS, ZIYO_MEBEL_GROUP_ID,
    WRITE_LIMIT, LINK_LIMIT, LINK_EXTRA
)

logger = logging.getLogger(__name__)
router = Router()

# URL pattern
URL_PATTERN = re.compile(
    r'(https?://|t\.me/|@\w+|www\.|tg://)',
    re.IGNORECASE
)

# APK pattern
APK_PATTERN = re.compile(r'\.apk$', re.IGNORECASE)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Guruh admini ekanligini tekshirish"""
    if user_id in ADMIN_IDS:
        return True
    # VIP guruh adminlari (botdan qo'shilgan)
    if await db.is_group_admin_vip(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ('administrator', 'creator')
    except Exception:
        return False


async def get_write_limit() -> int:
    val = await db.get_guard_setting('write_limit', str(WRITE_LIMIT))
    return int(val)


async def get_link_limit() -> int:
    val = await db.get_guard_setting('link_limit', str(LINK_LIMIT))
    return int(val)


async def get_link_extra() -> int:
    val = await db.get_guard_setting('link_extra', str(LINK_EXTRA))
    return int(val)


async def send_dm(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text, parse_mode='HTML')
    except Exception:
        pass


async def _delete_after(msg, delay: int):
    import asyncio
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def warn_in_group(bot: Bot, chat_id: int, user_id: int, username: str, full_name: str, reason: str):
    """Guruhda ogohlantirish — 5 soniyada o'chadi"""
    import asyncio
    mention = f"@{username}" if username else full_name
    try:
        msg = await bot.send_message(
            chat_id,
            f"{mention}, {reason}",
            parse_mode='HTML'
        )
        asyncio.create_task(_delete_after(msg, 5))
    except Exception:
        pass


# ─── GURUH XABARLARINI TEKSHIRISH ────────────────────────────

@router.message(F.chat.id == GROUP_ID)
async def guard_messages(message: Message, bot: Bot):
    if not message.from_user:
        return

    user = message.from_user
    user_id = user.id

    # Admin — hech narsa tekshirilmaydi
    if await is_group_admin(bot, message.chat.id, user_id):
        return

    ref_count = await db.get_referral_count(user_id)
    write_limit = await get_write_limit()
    link_limit = await get_link_limit()
    link_extra = await get_link_extra()

    # 1. APK tekshiruvi
    if message.document and message.document.file_name:
        if APK_PATTERN.search(message.document.file_name):
            try:
                await message.delete()
            except Exception:
                pass
            await send_dm(
                bot, user_id,
                "📵 <b>APK fayl taqiqlangan!</b>\n\n"
                "Guruhga APK fayl yuborib bo'lmaydi."
            )
            return

    # 2. Link tekshiruvi
    has_link = False
    if message.text and URL_PATTERN.search(message.text):
        has_link = True
    if message.caption and URL_PATTERN.search(message.caption):
        has_link = True
    if message.entities:
        for entity in message.entities:
            if entity.type in ('url', 'text_link', 'mention'):
                has_link = True
                break

    if has_link:
        if ref_count < link_limit:
            try:
                await message.delete()
            except Exception:
                pass
            need = link_limit - ref_count
            dm_text = (
                f"🔗 <b>Link tashlab bolmaydi!</b>\n\n"
                f"Guruhga link tashlash uchun <b>{link_limit} ta</b> odam qoshishingiz kerak.\n"
                f"Hozir: <b>{ref_count} ta</b> | Yetishmaydi: <b>{need} ta</b>\n\n"
                f"Linkingizni oling va tarqating: /mylink"
            )
            await send_dm(bot, user_id, dm_text)
            await warn_in_group(
                bot, message.chat.id, user_id,
                user.username, user.full_name,
                f"guruhga link tashlash uchun yana <b>{need} ta</b> odam qoshish kerak! /mylink"
            )
            return
        else:
            already_warned = await db.is_link_warned(user_id)
            if not already_warned:
                await db.set_link_warned(user_id)
                extra = await get_link_extra()
                try:
                    await message.delete()
                except Exception:
                    pass
                dm_text = (
                    f"Hali link tashlay olmaysiz!\n\n"
                    f"Yana <b>{extra} ta</b> odam qoshishingiz kerak.\n"
                    f"Davom eting: /mylink"
                )
                await send_dm(bot, user_id, dm_text)
                await warn_in_group(
                    bot, message.chat.id, user_id,
                    user.username, user.full_name,
                    f"yana <b>{extra} ta</b> odam qoshishingiz kerak! /mylink"
                )
                return

    # 3. Kalit so'z tekshiruvi
    if message.text:
        keywords = await db.get_keywords()
        text_lower = message.text.lower()
        found_word = None
        for kw in keywords:
            if kw in text_lower:
                found_word = kw
                break

        if found_word:
            if ref_count < link_limit:
                try:
                    await message.delete()
                except Exception:
                    pass
                need = link_limit - ref_count
                dm_text = (
                    f"Bu sozni ishlatib bolmaydi!\n\n"
                    f"Guruhda bu sozni ishlatish uchun <b>{link_limit} ta</b> odam qoshishingiz kerak.\n"
                    f"Hozir: <b>{ref_count} ta</b> | Yetishmaydi: <b>{need} ta</b>\n\n"
                    f"Linkingizni oling: /mylink"
                )
                await send_dm(bot, user_id, dm_text)
                await warn_in_group(
                    bot, message.chat.id, user_id,
                    user.username, user.full_name,
                    f"bu sozni ishlatish uchun yana <b>{need} ta</b> odam qoshish kerak! /mylink"
                )
                return

    # 4. Yozish chegarasi tekshiruvi
    if ref_count < write_limit:
        try:
            await message.delete()
        except Exception:
            pass
        need = write_limit - ref_count
        dm_text = (
            f"Yozish uchun odam qoshing!\n\n"
            f"Guruhda yozish uchun <b>{write_limit} ta</b> odam qoshishingiz kerak.\n"
            f"Hozir: <b>{ref_count} ta</b> | Yetishmaydi: <b>{need} ta</b>\n\n"
            f"Shaxsiy linkingizni oling: /mylink"
        )
        await send_dm(bot, user_id, dm_text)
        await warn_in_group(
            bot, message.chat.id, user_id,
            user.username, user.full_name,
            f"guruhda yozish uchun yana <b>{need} ta</b> odam qoshish kerak! /mylink"
        )
        return


# ─── ADMIN BUYRUQLARI ─────────────────────────────────────────

@router.message(Command("setlimit"))
async def set_write_limit(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /setlimit 5")
        return
    val = int(parts[1])
    await db.set_guard_setting('write_limit', str(val))
    await message.answer(f"Yozish chegarasi: <b>{val} ta</b> odam.", parse_mode='HTML')


@router.message(Command("setlinklimit"))
async def set_link_limit_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /setlinklimit 20")
        return
    val = int(parts[1])
    await db.set_guard_setting('link_limit', str(val))
    await message.answer(f"Link chegarasi: <b>{val} ta</b> odam.", parse_mode='HTML')


@router.message(Command("addword"))
async def add_word(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Format: /addword kalit_soz")
        return
    word = parts[1].strip().lower()
    await db.add_keyword(word)
    await message.answer(f"Kalit soz qoshildi: <b>{word}</b>", parse_mode='HTML')


@router.message(Command("delword"))
async def del_word(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Format: /delword kalit_soz")
        return
    word = parts[1].strip().lower()
    await db.remove_keyword(word)
    await message.answer(f"Kalit soz ochirildi: <b>{word}</b>", parse_mode='HTML')


@router.message(Command("words"))
async def list_words(message: Message):
    if not is_admin(message.from_user.id):
        return
    words = await db.get_keywords()
    if not words:
        await message.answer("Kalit sozlar yoq.")
        return
    text = "\n".join(f"• {w}" for w in words)
    await message.answer(f"<b>Kalit sozlar:</b>\n{text}", parse_mode='HTML')

@router.message(Command("addgroupadmin"))
async def add_group_admin_cmd(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip('-').isdigit():
        await message.answer(
            "Format: /addgroupadmin 123456789\n"
            "ID ni kiriting — o'sha odam guruhda cheklanmaydi."
        )
        return
    user_id = int(parts[1])
    await db.add_group_admin(user_id)

    # Ismini topishga harakat qilamiz
    try:
        member = await bot.get_chat_member(message.chat.id if message.chat.id == -1003371929345 else message.chat.id, user_id)
        name = member.user.full_name
    except Exception:
        u = await db.get_user(user_id)
        name = u['full_name'] if u else str(user_id)

    await message.answer(
        f"✅ <b>{name}</b> (<code>{user_id}</code>) guruh VIP adminiga qo'shildi.\n"
        f"Endi u guruhda cheklanmaydi.",
        parse_mode='HTML'
    )


@router.message(Command("removegroupadmin"))
async def remove_group_admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip('-').isdigit():
        await message.answer("Format: /removegroupadmin 123456789")
        return
    user_id = int(parts[1])
    await db.remove_group_admin(user_id)
    await message.answer(
        f"❌ <code>{user_id}</code> guruh VIP adminlaridan olib tashlandi.",
        parse_mode='HTML'
    )


@router.message(Command("groupadmins"))
async def list_group_admins(message: Message):
    if not is_admin(message.from_user.id):
        return
    admins = await db.get_group_admins()
    if not admins:
        await message.answer("Guruh VIP adminlari yo'q.\n\nQo'shish: /addgroupadmin ID")
        return
    lines = ["<b>Guruh VIP adminlari:</b>\n"]
    for uid in admins:
        u = await db.get_user(uid)
        name = u['full_name'] if u else "—"
        lines.append(f"• {name} — <code>{uid}</code>")
    lines.append(f"\nO'chirish: /removegroupadmin ID")
    await message.answer("\n".join(lines), parse_mode='HTML')