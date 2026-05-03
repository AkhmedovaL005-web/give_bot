import math
import logging
from datetime import datetime, timezone
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

import database as db
from config import (
    GROUP_ID, CHANNEL_URL, CHECK_CHANNEL,
    MIN_REFERRALS_FOR_RANDOM, ADMIN_IDS, DB_FILE,
    BACKUP_CHANNEL_ID, BOT_NAME, ZIYO_MEBEL_GROUP_ID, ZIYO_MEBEL_URL
)
from keyboards import user_menu, admin_menu, join_keyboard, pagination_keyboard, transfer_confirm
from utils import check_membership, user_mention, time_remaining

logger = logging.getLogger(__name__)
router = Router()

GROUP_INVITE_LINK = "https://t.me/+w-NZES_8zLRlZjc6"


class TransferState(StatesGroup):
    waiting_target = State()


async def get_invite(bot: Bot) -> str:
    try:
        group_info = await bot.get_chat(GROUP_ID)
        return group_info.invite_link or GROUP_INVITE_LINK
    except Exception:
        return GROUP_INVITE_LINK


async def is_member_check(bot: Bot, user_id: int) -> bool:
    # 1. Asosiy guruh + kanal tekshiruvi (check_membership ichida)
    if not await check_membership(bot, user_id):
        return False
    # 2. Binary Mind guruhi tekshiruvi
    try:
        m = await bot.get_chat_member(ZIYO_MEBEL_GROUP_ID, user_id)
        if m.status in ('left', 'kicked', 'banned'):
            return False
    except Exception:
        pass
    return True


# ─── START ───────────────────────────────────────────────────

async def handle_bal_request(message: Message, bot: Bot, token: str):
    """Bal so'rash havolasi — /start req_TOKEN"""
    user = message.from_user

    # Foydalanuvchini ro'yxatdan o'tkazamiz (a'zo bo'lmasa ham)
    await db.register_user(user.id, user.username, user.full_name)

    request = await db.get_bal_request(token)
    if not request:
        await message.answer("❌ Havola topilmadi yoki eskirgan.")
        return

    req_id, from_id, status = request

    if status != 'pending':
        await message.answer("❌ Bu so'rov allaqachon bajarilgan.")
        return

    if from_id == user.id:
        await message.answer("❌ O'zingizga so'rov yubora olmaysiz.")
        return

    from_user = await db.get_user(from_id)
    if not from_user:
        await message.answer("❌ So'rov yuborgan foydalanuvchi topilmadi.")
        return

    from_name = from_user['full_name']
    from_ref_count = await db.get_referral_count(from_id)
    my_ref_count = await db.get_referral_count(user.id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    if my_ref_count > 0:
        kb.button(
            text=f"✅ Ha, {my_ref_count} ta balimni beraman",
            callback_data=f"reqaccept:{token}:{from_id}:{user.id}"
        )
    kb.button(text="❌ Yo'q, rad etaman", callback_data="reqcancel")
    kb.adjust(1)

    if my_ref_count == 0:
        bal_text = "⚠️ Sizda hozir bal yo'q, shuning uchun bera olmaysiz."
    else:
        bal_text = f"Tasdiqlasangiz, <b>{my_ref_count} ta</b> balingiz unga o'tkaziladi."

    await message.answer(
        f"🎁 <b>{from_name}</b> sizdan bal so'rayapti!\n\n"
        f"Uning hozirgi bali: <b>{from_ref_count} ta</b>\n"
        f"Sizning balingiz: <b>{my_ref_count} ta</b>\n\n"
        f"{bal_text}",
        parse_mode='HTML',
        reply_markup=kb.as_markup()
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user

    # /start req_TOKEN — bal so'rash havolasi
    args = message.text.split()
    if len(args) >= 2 and args[1].startswith("req_"):
        token = args[1][4:]
        await handle_bal_request(message, bot, token)
        return

    if await db.is_blacklisted(user.id):
        await message.answer("🚫 Siz konkursdan mahrum etilgansiz.")
        return

    is_new = await db.register_user(user.id, user.username, user.full_name)
    is_admin = user.id in ADMIN_IDS

    # Arxiv kanalga faqat 1 marta yozish
    if is_new:
        # Avval kanalda bormi tekshirish
        already_backed = await db.is_user_backed_up(user.id)
        if not already_backed:
            await db.backup_user_to_channel(
                bot, user.id, user.full_name, user.username,
                BOT_NAME, BACKUP_CHANNEL_ID
            )
            await db.mark_user_backed_up(user.id)

    if not await is_member_check(bot, user.id):
        invite = await get_invite(bot)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        join_kb = InlineKeyboardBuilder()
        join_kb.button(text="👥 Guruhga qo'shilish", url=GROUP_INVITE_LINK)
        join_kb.button(text="📢 Kanalga qo'shilish", url=CHANNEL_URL)
        join_kb.button(text="🤖 Binary Mind guruhiga qo'shilish", url=ZIYO_MEBEL_URL)
        join_kb.button(text="✅ Tekshirish", callback_data="check_membership")
        join_kb.adjust(1)
        await message.answer(
            "👋 Assalomu alaykum!\n\n"
            "Botdan foydalanish uchun quyidagilarga abo boling:",
            reply_markup=join_kb.as_markup()
        )
        return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🎉 <b>TO'RAQO'RG'ON _ NATYAJNOY</b> Give Away botiga xush kelibsiz!\n\n"
        f"📌 Shaxsiy linkingizni oling va do'stlaringizni taklif qiling!\n"
        f"🏆 Eng ko'p odam qo'shgan Top 3 sovg'a yutadi!\n\n"
        f"👇 Pastdagi tugmalardan foydalaning:",
        reply_markup=admin_menu() if is_admin else user_menu(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_membership")
async def check_join(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    if await is_member_check(bot, user.id):
        await db.register_user(user.id, user.username, user.full_name)
        is_admin = user.id in ADMIN_IDS
        await callback.message.edit_text("✅ A'zolik tasdiqlandi!")
        await callback.message.answer(
            f"👋 Xush kelibsiz, <b>{user.full_name}</b>!\n\n"
            f"📌 Linkingizni oling va do'stlaringizni taklif qiling!\n\n"
            f"👇 Pastdagi tugmalardan foydalaning:",
            reply_markup=admin_menu() if is_admin else user_menu(),
            parse_mode='HTML'
        )
    else:
        invite = await get_invite(bot)
        await callback.answer(
            "❌ Hali a'zo emassiz! Guruh va kanalga qo'shiling.",
            show_alert=True
        )


# ─── LINK ────────────────────────────────────────────────────

@router.message(F.text == "🔗 Linkimni olish")
async def my_link(message: Message, bot: Bot):
    user = message.from_user

    if not await is_member_check(bot, user.id):
        invite = await get_invite(bot)
        await message.answer(
            "⚠️ Avval guruhga a'zo bo'ling!",
            reply_markup=join_keyboard(invite, CHANNEL_URL if CHECK_CHANNEL else None)
        )
        return

    if await db.is_blacklisted(user.id):
        await message.answer("🚫 Siz konkursdan mahrum etilgansiz.")
        return

    gw = await db.get_giveaway()
    if not gw or not gw['is_active']:
        await message.answer("ℹ️ Hozirda faol give away yo'q.")
        return

    existing = await db.get_invite_link(user.id)
    if existing:
        link = existing
    else:
        try:
            invite = await bot.create_chat_invite_link(
                GROUP_ID,
                name=f"ref_{user.id}",
                creates_join_request=False
            )
            link = invite.invite_link
            await db.save_invite_link(user.id, link)
            await db.set_link_sent(user.id)
        except Exception as e:
            logger.error(f"Link yaratishda xato: {e}")
            await message.answer(
                "❌ Link yaratishda xato!\n"
                "Bot guruhda admin bo'lishi va 'Invite users via link' huquqi bo'lishi kerak."
            )
            return

    ref_count = await db.get_referral_count(user.id)
    time_left = "—"
    if gw and gw['ends_at']:
        ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
        time_left = time_remaining(ends)

    await message.answer(
        f"🔗 <b>Sizning shaxsiy taklif linkingiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Qo'shgan odamlar: <b>{ref_count} ta</b>\n"
        f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
        f"💡 Shu linkni do'stlaringizga yuboring!\n"
        f"Kim shu link orqali kirsa — siz ball olasiz! 🏆",
        parse_mode='HTML'
    )


# ─── ACHKOLARIM ──────────────────────────────────────────────

@router.message(F.text == "👥 Achkolarim")
async def my_invites(message: Message, bot: Bot):
    if not await is_member_check(bot, message.from_user.id):
        invite = await get_invite(bot)
        await message.answer(
            "⚠️ Avval guruhga a'zo bo'ling!",
            reply_markup=join_keyboard(invite, CHANNEL_URL if CHECK_CHANNEL else None)
        )
        return
    await show_invites_page(message, message.from_user.id, page=1)


async def show_invites_page(message: Message, user_id: int, page: int):
    per_page = 50
    offset = (page - 1) * per_page
    rows = await db.get_referrals_list(user_id, offset=offset, limit=per_page)
    total = await db.get_referral_count(user_id)
    total_pages = max(1, math.ceil(total / per_page))
    rank = await db.get_user_rank(user_id)

    if not rows:
        await message.answer(
            "👥 Hali hech kimni qo'shmadingiz.\n\n"
            "🔗 Linkingizni oling va tarqating!"
        )
        return

    lines = [f"👥 <b>Sizning achkolaringiz</b> ({total} ta) | 🏆 {rank}-o'rin\n"]
    for i, (full_name, username, joined_at) in enumerate(rows, offset + 1):
        uname = f"@{username}" if username else "—"
        lines.append(f"{i}. {full_name} — {uname}")

    kb = pagination_keyboard(page, total_pages, f"invites:{user_id}") if total_pages > 1 else None
    await message.answer("\n".join(lines), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith("invites:"))
async def invites_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    page = int(parts[2])
    await callback.message.delete()
    await show_invites_page(callback.message, user_id, page)
    await callback.answer()


# ─── BAL BERISH ──────────────────────────────────────────────

@router.message(F.text == "🎁 Bal berish")
async def give_points_start(message: Message, state: FSMContext, bot: Bot):
    if not await is_member_check(bot, message.from_user.id):
        invite = await get_invite(bot)
        await message.answer(
            "⚠️ Avval guruhga a'zo bo'ling!",
            reply_markup=join_keyboard(invite, CHANNEL_URL if CHECK_CHANNEL else None)
        )
        return

    user = message.from_user
    u = await db.get_user(user.id)

    if u and u['transfer_done']:
        await message.answer(
            "❌ Siz allaqachon balingizni berdingiz.\n"
            "Bu bir martalik imkoniyat."
        )
        return

    ref_count = await db.get_referral_count(user.id)
    if ref_count == 0:
        await message.answer(
            "❌ Sizda beradigan ball yo'q.\n"
            "Avval do'stlaringizni taklif qiling!"
        )
        return

    await state.set_state(TransferState.waiting_target)
    await state.update_data(ref_count=ref_count)

    await message.answer(
        f"👥 Sizda <b>{ref_count} ta</b> ball bor.\n\n"
        f"Kimga berishni xohlaysiz?\n"
        f"Username yoki ID yuboring:\n\n"
        f"Misol: <code>@username</code> yoki <code>123456789</code>\n\n"
        f"Bekor qilish: /cancel",
        parse_mode='HTML'
    )


@router.message(TransferState.waiting_target)
async def give_points_target(message: Message, state: FSMContext):
    data = await state.get_data()
    ref_count = data.get('ref_count', 0)
    text = message.text.strip().lstrip('@')

    if text == '/cancel':
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    target = None
    async with aiosqlite.connect(DB_FILE) as conn:
        if text.lstrip('-').isdigit():
            async with conn.execute(
                "SELECT user_id, full_name FROM users WHERE user_id=?", (int(text),)
            ) as c:
                row = await c.fetchone()
        else:
            async with conn.execute(
                "SELECT user_id, full_name FROM users WHERE username=?", (text,)
            ) as c:
                row = await c.fetchone()

    if row:
        target = {'user_id': row[0], 'full_name': row[1]}

    if not target:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.\n"
            "Username yoki ID ni to'g'ri kiriting."
        )
        return

    if target['user_id'] == message.from_user.id:
        await message.answer("❌ O'zingizga bera olmaysiz.")
        return

    await state.update_data(target_id=target['user_id'], target_name=target['full_name'])

    await message.answer(
        f"⚠️ <b>Tasdiqlaysizmi?</b>\n\n"
        f"<b>{ref_count} ta</b> ball → {user_mention(target['full_name'], target['user_id'])}\n\n"
        f"⚠️ Bu <b>bir martalik</b> amal. Qaytarib bo'lmaydi!",
        parse_mode='HTML',
        reply_markup=transfer_confirm(target['full_name'], ref_count)
    )


@router.callback_query(F.data == "confirm:transfer")
async def confirm_transfer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get('target_id')
    target_name = data.get('target_name')
    ref_count = data.get('ref_count', 0)

    success = await db.transfer_points(callback.from_user.id, target_id)
    await state.clear()

    if success:
        new_count = await db.get_referral_count(target_id)
        await callback.message.edit_text(
            f"✅ Ball muvaffaqiyatli o'tkazildi!\n"
            f"→ {target_name} endi <b>{new_count} ta</b> ballga ega.",
            parse_mode='HTML'
        )
        try:
            await bot.send_message(
                target_id,
                f"🎁 {user_mention(callback.from_user.full_name, callback.from_user.id)} "
                f"sizga <b>{ref_count} ta</b> ball o'tkazdi!\n"
                f"Endi sizda <b>{new_count} ta</b> ball bor. 🏆",
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        await callback.message.edit_text(
            "❌ Transfer amalga oshmadi. Allaqachon bergan bo'lishingiz mumkin."
        )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# ─── BUYRUQLAR ───────────────────────────────────────────────

@router.message(F.text == "/mylink")
async def cmd_mylink(message: Message, bot: Bot):
    await my_link(message, bot)


@router.message(F.text == "/mystats")
async def cmd_mystats(message: Message):
    user = message.from_user
    ref_count = await db.get_referral_count(user.id)
    rank = await db.get_user_rank(user.id)
    gw = await db.get_giveaway()

    if ref_count >= MIN_REFERRALS_FOR_RANDOM:
        random_status = "✅ Random sovga uchun huquqingiz bor!"
    else:
        need = MIN_REFERRALS_FOR_RANDOM - ref_count
        random_status = f"🎲 Random sovgaga yana <b>{need} ta</b> odam yetishmayapti!"

    time_left = "—"
    if gw and gw['is_active'] and gw['ends_at']:
        ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
        time_left = time_remaining(ends)

    await message.answer(
        (
            "📊 <b>Sizning statistikangiz</b>\n\n"
            + f"👥 Qoshgan odamlar: <b>{ref_count} ta</b>\n"
            + f"🏆 Orningiz: <b>{rank}-orin</b>\n"
            + f"Tugashiga: <b>{time_left}</b>\n\n"
            + random_status
        ),
        parse_mode='HTML'
    )


@router.message(F.text == "/myinvites")
async def cmd_myinvites(message: Message):
    await show_invites_page(message, message.from_user.id, page=1)


# ─── BAL SO'RASH ─────────────────────────────────────────────

@router.message(F.text == "/request")
async def request_bal(message: Message, bot: Bot):
    user = message.from_user

    if not await is_member_check(bot, user.id):
        await message.answer("Avval guruhga a'zo bo'ling!")
        return

    ref_count = await db.get_referral_count(user.id)

    import secrets
    token = secrets.token_urlsafe(12)
    await db.create_bal_request(user.id, token)

    bot_info = await bot.get_me()
    deep_link = "https://t.me/" + bot_info.username + "?start=req_" + token

    # Ulashish tugmasi — Telegram share dialog ochadi
    import urllib.parse
    share_text = (
        f"🎁 {user.full_name} sizdan bal so'rayapti!\n"
        f"Quyidagi havolani bosib yordamingizni bering 👇"
    )
    share_url = "https://t.me/share/url?url=" + urllib.parse.quote(deep_link) + "&text=" + urllib.parse.quote(share_text)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Do'stlarga ulashish", url=share_url)
    kb.adjust(1)

    await message.answer(
        f"🎁 <b>Bal so'rash</b>\n\n"
        f"Sizning hozirgi balingiz: <b>{ref_count} ta</b>\n\n"
        f"Quyidagi tugmani bosing → chatni tanlang → xabar yuboring.\n"
        f"Do'stingiz havola orqali kirsa, balini sizga o'tkazish imkoni chiqadi.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("reqaccept:"))
async def accept_request(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    token = parts[1]
    to_id = int(parts[2])    # so'rov yuborgan (bal oluvchi)
    from_id = int(parts[3])  # bal beruvchi

    request = await db.get_bal_request(token)
    if not request or request[2] != 'pending':
        await callback.answer("❌ Bu so'rov allaqachon bajarilgan.", show_alert=True)
        return

    my_bal = await db.get_referral_count(from_id)
    if my_bal == 0:
        await callback.answer("❌ Sizda beradigan ball yo'q.", show_alert=True)
        return

    ADMIN_LIMIT = 200

    if my_bal > ADMIN_LIMIT:
        # Adminlarga tasdiqlash uchun yuborish
        from config import ADMIN_IDS
        from utils import user_mention

        from_user = await db.get_user(from_id)
        to_user = await db.get_user(to_id)
        from_name = from_user['full_name'] if from_user else str(from_id)
        to_name = to_user['full_name'] if to_user else str(to_id)

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Tasdiqlash", callback_data=f"reqadmin:approve:{token}:{to_id}:{from_id}:{my_bal}")
        kb.button(text="❌ Bekor qilish", callback_data=f"reqadmin:reject:{token}:{to_id}:{from_id}")
        kb.button(text="🚫 Ikkalasini ban", callback_data=f"reqadmin:ban:{token}:{to_id}:{from_id}")
        kb.adjust(1)

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    (
                        "<b>KATTA TRANSFER TASDIQLASH KERAK!</b>\n\n"
                        f"Miqdor: <b>{my_bal} ta bal</b> (200 dan ortiq)\n\n"
                        f"Beruvchi: {user_mention(from_name, from_id)}\n"
                        f"ID: <code>{from_id}</code>\n\n"
                        f"Oluvchi: {user_mention(to_name, to_id)}\n"
                        f"ID: <code>{to_id}</code>"
                    ),
                    parse_mode='HTML',
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass

        await db.update_bal_request_status(token, 'pending_admin')
        await callback.message.edit_text(
            f"Admin tasdiqlashi kerak ({my_bal} ta bal).\n"
            "Tez orada javob berishadi!",
            parse_mode='HTML'
        )
    else:
        # To'g'ridan to'g'ri o'tkazish
        import aiosqlite
        from config import DB_FILE
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.execute("DELETE FROM referrals WHERE referrer_id=?", (from_id,))
            for i in range(my_bal):
                fake_id = -(to_id * 10000 + from_id * 100 + i)
                try:
                    await conn.execute(
                        "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                        (to_id, fake_id)
                    )
                except Exception:
                    pass
            await conn.commit()

        await db.update_bal_request_status(token, 'done')

        to_user = await db.get_user(to_id)
        to_name = to_user['full_name'] if to_user else str(to_id)
        new_count = await db.get_referral_count(to_id)

        await callback.message.edit_text(
            f"Muvaffaqiyatli! {my_bal} ta bal {to_name} ga otkazildi.\n"
            f"Yangi bali: <b>{new_count} ta</b>",
            parse_mode='HTML'
        )

        try:
            await bot.send_message(
                to_id,
                f"Bal olindi! {my_bal} ta bal sizga otkazildi.\n"
                f"Endi sizda <b>{new_count} ta</b> ball bor.",
                parse_mode='HTML'
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                from_id,
                f"✅ Siz {to_name} ga <b>{my_bal} ta bal</b> berdingiz.",
                parse_mode='HTML'
            )
        except Exception:
            pass


@router.callback_query(F.data == "reqcancel")
async def cancel_request(callback: CallbackQuery, bot: Bot):
    # So'rovni rad etdi — token ni topib 'rejected' qilamiz
    # Xabardan from_name ni olamiz, tugmalarni olib tashlaymiz
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Rad etildi.</b>",
        parse_mode='HTML'
    )
    await callback.answer("Rad etdingiz.", show_alert=False)

    # So'rov yuboruvchiga xabar beramiz (callback datada from_id yo'q, shuning uchun DB dan topamiz)
    # Xabar matnidan nomni olib, foydalanuvchini topishga harakat qilamiz — shart emas, skip qilamiz
    await callback.answer()