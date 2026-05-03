import io
import logging
import random
from datetime import datetime, timezone
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import (
    ADMIN_IDS, GROUP_ID, GROUP_ID, TOP_WINNERS_COUNT,
    TOP_RANDOM_POOL_START, TOP_RANDOM_POOL_END, TOP_RANDOM_COUNT,
    GLOBAL_RANDOM_COUNT, MIN_REFERRALS_FOR_RANDOM, BACKUP_WINNERS_COUNT
)
from filters import IsAdmin
from keyboards import end_giveaway_confirm, winner_contact_keyboard
from utils import (
    send_to_admins, build_leaderboard_text, format_dt,
    time_remaining, user_mention, generate_csv, now_local
)

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())


class BalState(StatesGroup):
    waiting_user = State()
    waiting_amount = State()


class GiveawaySetup(StatesGroup):
    start_time = State()
    end_time = State()
    confirm = State()


class BroadcastState(StatesGroup):
    waiting_text = State()


class SendAllState(StatesGroup):
    waiting_text = State()


class WriteUserState(StatesGroup):
    waiting_user_id = State()
    waiting_text = State()


class BanState(StatesGroup):
    waiting_user = State()


# ─── GIVE AWAY BOSHLASH ──────────────────────────────────────

@router.message(F.text == "🚀 Give Away boshlash")
async def start_giveaway_cmd(message: Message, state: FSMContext):
    gw = await db.get_giveaway()
    if gw and gw['is_active']:
        await message.answer("⚠️ Give away allaqachon faol! Avval tugatish kerak.")
        return
    await state.set_state(GiveawaySetup.start_time)
    await message.answer(
        "📅 <b>Give away boshlanish vaqtini kiriting:</b>\n\n"
        "Format: <code>25.01.2025 20:00</code>\n"
        "⏰ Toshkent vaqti (UTC+5) da kiriting",
        parse_mode='HTML'
    )


@router.message(GiveawaySetup.start_time)
async def gw_get_start(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(started_at=dt)
        await state.set_state(GiveawaySetup.end_time)
        await message.answer(
            "📅 <b>Tugash vaqtini kiriting:</b>\n\n"
            "Format: <code>02.02.2025 20:00</code>\n"
            "⚠️ Kamida 1 kun, ko'pi bilan 60 kun bo'lishi kerak",
            parse_mode='HTML'
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n"
            "To'g'ri misol: <code>25.01.2025 20:00</code>",
            parse_mode='HTML'
        )


@router.message(GiveawaySetup.end_time)
async def gw_get_end(message: Message, state: FSMContext):
    try:
        end_dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        data = await state.get_data()
        start_dt = data['started_at']

        if end_dt <= start_dt:
            await message.answer("❌ Tugash vaqti boshlanishdan keyin bo'lishi kerak!")
            return

        diff = end_dt - start_dt
        if diff.days > 60:
            await message.answer("❌ Davomiylik 60 kundan oshmasligi kerak!")
            return

        await state.update_data(ends_at=end_dt)
        await state.set_state(GiveawaySetup.confirm)

        days = diff.days
        hours = diff.seconds // 3600

        await message.answer(
            f"✅ <b>Tekshirib ko'ring:</b>\n\n"
            f"🚀 Boshlanish: <b>{start_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n"
            f"🏁 Tugash: <b>{end_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n"
            f"⏳ Davomiyligi: <b>{days} kun {hours} soat</b>\n\n"
            f"Tasdiqlaysizmi?",
            parse_mode='HTML',
            reply_markup=_confirm_start_kb()
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n"
            "To'g'ri misol: <code>02.02.2025 20:00</code>",
            parse_mode='HTML'
        )


def _confirm_start_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, boshlash", callback_data="confirm:start_giveaway")
    kb.button(text="❌ Bekor", callback_data="cancel_setup")
    kb.adjust(2)
    return kb.as_markup()


@router.callback_query(F.data == "confirm:start_giveaway")
async def confirm_start_giveaway(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    start_dt = data['started_at']
    end_dt = data['ends_at']
    await state.clear()

    # UTC ga o'tkazish (Toshkent UTC+5)
    from datetime import timedelta
    start_utc = start_dt - timedelta(hours=5)
    end_utc = end_dt - timedelta(hours=5)

    await db.start_giveaway(start_utc, end_utc)

    await callback.message.edit_text(
        f"🎉 <b>Give Away boshlandi!</b>\n\n"
        f"🚀 Boshlanish: {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"🏁 Tugash: {end_dt.strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )

    # Guruhga e'lon
    try:
        await bot.send_message(
            GROUP_ID,
            f"🎉 <b>GIVE AWAY BOSHLANDI!</b>\n\n"
            f"🏁 Tugash: <b>{end_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n\n"
            f"🏆 Top 3 sovrin oladi!\n"
            f"🎲 Random sovg'alar ham bor!\n\n"
            f"📌 Qatnashish uchun guruhga odam qo'shing!\n"
            f"🤖 Bot: @give_mebot",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Guruhga xabar yuborib bo'lmadi: {e}")


@router.callback_query(F.data == "cancel_setup")
async def cancel_setup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")


# ─── GIVE AWAY TUGATISH ──────────────────────────────────────

@router.message(F.text == "⛔ Tugatish")
async def end_giveaway_cmd(message: Message):
    gw = await db.get_giveaway()
    if not gw or not gw['is_active']:
        await message.answer("ℹ️ Hozirda faol give away yo'q.")
        return
    await message.answer(
        "⚠️ <b>Give awayni vaqtidan oldin tugatmoqchimisiz?</b>\n\n"
        "G'oliblar hoziroq e'lon qilinadi!",
        parse_mode='HTML',
        reply_markup=end_giveaway_confirm()
    )


@router.callback_query(F.data == "confirm:end_giveaway")
async def confirm_end_giveaway(callback: CallbackQuery, bot: Bot):
    await callback.message.edit_text("⏳ G'oliblar aniqlanmoqda...")
    await announce_winners(bot)


# ─── G'OLIBLARNI E'LON QILISH ────────────────────────────────

async def announce_winners(bot: Bot):
    """Asosiy g'oliblarni aniqlash va e'lon qilish"""
    await db.finish_giveaway()
    await db.revoke_all_invite_links(bot, GROUP_ID)

    won_ids = []

    # 1. Top 3
    top = await db.get_top_winners(TOP_WINNERS_COUNT)
    top_text = ["🏆 <b>GIVE AWAY YAKUNLANDI!</b>\n\n🥇 <b>ASOSIY G'OLIBLAR:</b>\n"]
    for i, (uid, username, full_name, cnt) in enumerate(top, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        top_text.append(f"{medals[i]} {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'top', rank=i)
        won_ids.append(uid)

        # Zaxira g'oliblar
        zaxira = await db.get_top_winners(TOP_WINNERS_COUNT + BACKUP_WINNERS_COUNT)
        for j, (buid, _, bname, _) in enumerate(zaxira[TOP_WINNERS_COUNT:], 1):
            await db.save_winner(buid, 'top_backup', rank=i + j, backup=True)

    # 2. Top 4-10 dan random
    pool_winners = await db.get_random_pool_winners(
        TOP_RANDOM_POOL_START, TOP_RANDOM_POOL_END, TOP_RANDOM_COUNT, won_ids
    )
    random_text = ["\n\n🎲 <b>RANDOM SOVG'A (Top 4-10):</b>\n"]
    for uid, username, full_name, cnt in pool_winners:
        random_text.append(f"🎁 {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'pool_random')
        won_ids.append(uid)

    # 3. Global random
    global_winner = await db.get_global_random_winner(won_ids, MIN_REFERRALS_FOR_RANDOM)
    global_text = ["\n\n🌟 <b>UMUMIY RANDOM G'OLIB:</b>\n"]
    if global_winner:
        uid, username, full_name, cnt = global_winner
        global_text.append(f"🌟 {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'global_random')
        won_ids.append(uid)
    else:
        global_text.append("Hech kim shart bajarмadi")

    full_text = (
        "".join(top_text) +
        "".join(random_text) +
        "".join(global_text) +
        "\n\n🎊 Tabriklaymiz!"
    )

    # Guruhga e'lon
    try:
        await bot.send_message(GROUP_ID, full_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Guruhga e'lon yuborib bo'lmadi: {e}")

    # G'oliblarga DM
    winners = await db.get_winners()
    for uid, prize_type, rank, username, full_name in winners:
        prize_names = {
            'top': f"🥇 {rank}-o'rin sovrin",
            'pool_random': "🎲 Random sovg'a (top 4-10)",
            'global_random': "🌟 Umumiy random sovg'a"
        }
        try:
            await bot.send_message(
                uid,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Siz <b>Give Away</b> da <b>{prize_names.get(prize_type, 'sovrin')}</b>ni yutdingiz!\n\n"
                f"Admin tez orada siz bilan bog'lanadi. 📩",
                parse_mode='HTML'
            )
        except Exception:
            pass

    # Adminlarga g'oliblar ro'yxati va kontaktlar
    admin_text = ["📋 <b>G'OLIBLAR KONTAKTLARI:</b>\n"]
    for uid, prize_type, rank, username, full_name in winners:
        uname = f"@{username}" if username else "username yo'q"
        admin_text.append(
            f"\n{'🥇🥈🥉'[rank-1] if rank and rank <= 3 else '🎁'} {full_name}\n"
            f"   {uname} | ID: <code>{uid}</code>"
        )

    await send_to_admins(
        bot,
        "".join(admin_text),
        parse_mode='HTML'
    )

    # Har bir g'olib uchun alohida "yozish" tugmasi
    for uid, prize_type, rank, username, full_name in winners:
        await send_to_admins(
            bot,
            f"👤 {user_mention(full_name, uid)} ({prize_type})",
            parse_mode='HTML'
        )


# ─── REKLAMA ─────────────────────────────────────────────────

@router.message(F.text == "📢 Reklama")
async def broadcast_start(message: Message, state: FSMContext):
    await state.set_state(BroadcastState.waiting_text)
    await message.answer(
        "✍️ Reklama xabarini yuboring (matn, rasm yoki video bo'lishi mumkin):\n\n"
        "Bekor qilish: /cancel"
    )


@router.message(BroadcastState.waiting_text)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Reklama bekor qilindi.")
        return
    await state.clear()
    users = await db.get_all_active_users()
    success = 0
    failed = 0
    status_msg = await message.answer(f"📢 Yuborilmoqda... (0/{len(users)})")

    for i, user_id in enumerate(users):
        try:
            await message.copy_to(user_id)
            success += 1
        except Exception:
            failed += 1
            await db.set_bot_blocked(user_id, True)

        if i % 50 == 0:
            try:
                await status_msg.edit_text(f"📢 Yuborilmoqda... ({i}/{len(users)})")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Reklama yakunlandi!\n"
        f"✔️ Muvaffaqiyatli: {success}\n"
        f"❌ Yuborilmadi: {failed}"
    )


# ─── ADMIN STATISTIKA ────────────────────────────────────────

@router.message(F.text.in_(["📈 Admin statistika", "📈 Админ статистика"]))
async def admin_stats(message: Message):
    total_users = await db.get_total_users()
    total_refs = await db.get_total_referrals()
    today_joins = await db.get_today_joins()
    top = await db.get_leaderboard(3)
    gw = await db.get_giveaway()

    gw_status = "✅ Faol" if gw and gw['is_active'] else "❌ Faol emas"
    time_left = "—"
    if gw and gw['is_active'] and gw['ends_at']:
        ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
        time_left = time_remaining(ends)

    top_text = ""
    for i, (uid, username, full_name, cnt) in enumerate(top, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        top_text += f"\n{medals[i]} {full_name} — {cnt} ta"

    await message.answer(
        f"📈 <b>ADMIN STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🔗 Jami referrallar: <b>{total_refs}</b>\n"
        f"📅 Bugun qo'shildi: <b>{today_joins}</b>\n\n"
        f"🎮 Give Away: {gw_status}\n"
        f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
        f"🏆 Hozirgi Top 3:{top_text}",
        parse_mode='HTML'
    )


# ─── G'OLIBLAR ───────────────────────────────────────────────

@router.message(F.text == "🏆 G'oliblar")
async def show_winners(message: Message):
    winners = await db.get_winners()
    if not winners:
        await message.answer("ℹ️ Hali g'oliblar aniqlanmagan.")
        return

    text = ["🏆 <b>G'OLIBLAR:</b>\n"]
    for uid, prize_type, rank, username, full_name in winners:
        uname = f"@{username}" if username else "username yo'q"
        prize_names = {
            'top': f"{rank}-o'rin",
            'pool_random': "Random (top 4-10)",
            'global_random': "Global random"
        }
        text.append(f"\n👤 {full_name} ({uname})\n   {prize_names.get(prize_type, '?')}")

    await message.answer("\n".join(text), parse_mode='HTML')

    # Har bir g'olib uchun kontakt tugmasi
    for uid, prize_type, rank, username, full_name in winners:
        await message.answer(
            f"👤 {user_mention(full_name, uid)}",
            parse_mode='HTML',
            reply_markup=winner_contact_keyboard(uid)
        )


# ─── BACKUP ──────────────────────────────────────────────────

@router.message(F.text == "💾 Backup olish")
async def manual_backup(message: Message, bot: Bot):
    await send_backup(bot, message.from_user.id)


async def send_backup(bot: Bot, chat_id: int = None):
    from config import ADMIN_IDS
    users_data, referrals_data = await db.export_all_data()
    csv_bytes = await generate_csv(users_data, referrals_data)

    now = datetime.now()
    filename = f"backup_{now.strftime('%Y%m%d_%H%M')}.csv"

    targets = [chat_id] if chat_id else ADMIN_IDS
    for admin_id in targets:
        try:
            await bot.send_document(
                admin_id,
                BufferedInputFile(csv_bytes.getvalue(), filename=filename),
                caption=(
                    f"💾 <b>Ma'lumotlar zaxirasi</b>\n"
                    f"📅 {now.strftime('%d.%m.%Y %H:%M')}\n"
                    f"👥 Foydalanuvchilar: {len(users_data)}\n"
                    f"🔗 Referrallar: {len(referrals_data)}"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Backup yuborib bo'lmadi {admin_id}: {e}")


# ─── FOYDALANUVCHIGA YOZISH ─────────────────────────────────

@router.message(F.text == "✉️ Foydalanuvchiga yozish")
async def write_user_start(message: Message, state: FSMContext):
    await state.set_state(WriteUserState.waiting_user_id)
    await message.answer(
        "👤 Kimga yozmoqchisiz?\n"
        "Username yoki ID yuboring:\n\n"
        "Misol: <code>@username</code> yoki <code>123456789</code>\n\n"
        "Bekor qilish: /cancel",
        parse_mode="HTML"
    )


@router.message(WriteUserState.waiting_user_id)
async def write_user_get_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    text = message.text.strip().lstrip("@")
    import aiosqlite
    from config import DB_FILE
    target = None
    async with aiosqlite.connect(DB_FILE) as conn:
        if text.lstrip("-").isdigit():
            async with conn.execute(
                "SELECT user_id, full_name, username FROM users WHERE user_id=?", (int(text),)
            ) as c:
                row = await c.fetchone()
        else:
            async with conn.execute(
                "SELECT user_id, full_name, username FROM users WHERE username=?", (text,)
            ) as c:
                row = await c.fetchone()
    if row:
        target = {"user_id": row[0], "full_name": row[1], "username": row[2]}

    if not target:
        await message.answer("❌ Foydalanuvchi topilmadi. Qaytadan kiriting yoki /cancel")
        return

    uname = f"@{target['username']}" if target["username"] else "username yoq"
    await state.update_data(target_id=target["user_id"], target_name=target["full_name"])
    await state.set_state(WriteUserState.waiting_text)
    await message.answer(
        f"✅ Topildi: <b>{target['full_name']}</b> ({uname})\n\n"
        f"Endi xabaringizni yozing (matn, rasm, video):\n\n"
        f"Bekor qilish: /cancel",
        parse_mode="HTML"
    )


@router.message(WriteUserState.waiting_text)
async def write_user_send(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    target_name = data.get("target_name")
    await state.clear()

    try:
        await message.copy_to(target_id)
        await message.answer(
            f"✅ Xabar <b>{target_name}</b> ga yuborildi!",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Yuborib bolmadi: {e}")


# ─── BAN ─────────────────────────────────────────────────────

@router.message(F.text == "🚫 Ban")
async def ban_start(message: Message, state: FSMContext):
    await state.set_state(BanState.waiting_user)
    await message.answer(
        "🚫 Ban qilish uchun username yoki ID yuboring:\n"
        "Misol: <code>@username</code> yoki <code>123456789</code>\n\n"
        "Banni ochish uchun: <code>unban @username</code>",
        parse_mode='HTML'
    )


@router.message(BanState.waiting_user)
async def ban_user(message: Message, state: FSMContext):
    await state.clear()
    text = message.text.strip()
    unban = text.lower().startswith('unban')
    if unban:
        text = text[5:].strip().lstrip('@')
    else:
        text = text.lstrip('@')

    # Foydalanuvchini topish
    async with __import__('aiosqlite').connect(__import__('config').DB_FILE) as conn:
        if text.lstrip('-').isdigit():
            async with conn.execute("SELECT user_id, full_name FROM users WHERE user_id=?", (int(text),)) as c:
                row = await c.fetchone()
        else:
            async with conn.execute("SELECT user_id, full_name FROM users WHERE username=?", (text,)) as c:
                row = await c.fetchone()

    if not row:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    uid, full_name = row
    await db.blacklist_user(uid, not unban)
    action = "bandi ochildi ✅" if unban else "ban qilindi 🚫"
    await message.answer(f"👤 {full_name} ({uid}) — {action}")




# ─── SENDALL ─────────────────────────────────────────────────

@router.message(F.text == "📡 Hammaga yuborish")
async def sendall_start(message: Message, state: FSMContext):
    from config import BROADCAST_CHATS
    await state.set_state(SendAllState.waiting_text)
    chat_count = len(BROADCAST_CHATS)
    await message.answer(
        f"Hammaga yuborish\n\n"
        f"Xabar barcha foydalanuvchilar + {chat_count} ta kanal/guruhga yuboriladi.\n\n"
        "Xabaringizni yuboring (matn, rasm, video):\n"
        "Bekor qilish: /cancel",
        parse_mode='HTML'
    )


@router.message(SendAllState.waiting_text)
async def sendall_send(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    await state.clear()
    from config import BROADCAST_CHATS

    # Foydalanuvchilarga yuborish
    users = await db.get_all_active_users()
    user_success = 0
    user_failed = 0
    total_users = len(users)
    total_chats = len(BROADCAST_CHATS)
    status_msg = await message.answer(
        f"Yuborilmoqda...\n"
        f"Foydalanuvchilar: 0/{total_users}\n"
        f"Kanal/guruhlar: 0/{total_chats}"
    )

    for i, user_id in enumerate(users):
        try:
            await message.copy_to(user_id)
            user_success += 1
        except Exception:
            user_failed += 1
            await db.set_bot_blocked(user_id, True)

        if i % 30 == 0:
            try:
                await status_msg.edit_text(
                    f"Yuborilmoqda...\n"
                    f"Foydalanuvchilar: {i}/{total_users}\n"
                    f"Kanal/guruhlar: 0/{total_chats}"
                )
            except Exception:
                pass

    # Kanal va guruhlarga yuborish
    chat_success = 0
    chat_failed = 0
    for chat_id in BROADCAST_CHATS:
        try:
            await message.copy_to(chat_id)
            chat_success += 1
        except Exception as e:
            chat_failed += 1

    await status_msg.edit_text(
        f"Hammaga yuborildi!\n\n"
        f"Foydalanuvchilar:\n"
        f"Muvaffaqiyatli: {user_success}\n"
        f"Yuborilmadi: {user_failed}\n\n"
        f"Kanal/guruhlar:\n"
        f"Muvaffaqiyatli: {chat_success}\n"
        f"Yuborilmadi: {chat_failed}",
        parse_mode='HTML'
    )

# ─── CANCEL ──────────────────────────────────────────────────

@router.message(F.text == "/cancel")
async def cancel_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.")


# ─── BAL BOSHQARUV ───────────────────────────────────────────

@router.message(F.text == "⚖️ Bal boshqaruv")
async def bal_menu(message: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Barchanikini 0 ga tushirish", callback_data="bal:reset_all")
    kb.button(text="➕ Biriga bal qo'shish", callback_data="bal:add")
    kb.button(text="➖ Biriga bal ayirish", callback_data="bal:subtract")
    kb.adjust(1)
    await message.answer("⚖️ <b>Bal boshqaruv:</b>", parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == "bal:reset_all")
async def bal_reset_confirm(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Ha, barchanikini 0 ga tushir", callback_data="bal:confirm_reset")
    kb.button(text="❌ Bekor", callback_data="cancel")
    kb.adjust(1)
    await callback.message.edit_text(
        "⚠️ <b>Ishonchingiz komilmi?</b>\n\n"
        "Barcha foydalanuvchilarning ballari 0 ga tushiriladi!\n"
        "Bu amalni qaytarib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "bal:confirm_reset")
async def bal_reset_all(callback: CallbackQuery):
    async with __import__('aiosqlite').connect(__import__('config').DB_FILE) as db:
        await db.execute("DELETE FROM referrals")
        await db.execute("UPDATE users SET transfer_done=0")
        await db.commit()
    await callback.message.edit_text(
        "✅ Barcha ballar 0 ga tushirildi!\n"
        "Transfer imkoniyatlari ham yangilandi."
    )


@router.callback_query(F.data.in_(["bal:add", "bal:subtract"]))
async def bal_change_start(callback: CallbackQuery, state: FSMContext):
    action = "qo'shish" if callback.data == "bal:add" else "ayirish"
    await state.set_state(BalState.waiting_user)
    await state.update_data(action=callback.data)
    await callback.message.edit_text(
        f"👤 Kimning baliga {action} xohlaysiz?\n"
        f"Username yoki ID yuboring:\n\n"
        f"Misol: <code>@username</code>",
        parse_mode="HTML"
    )


@router.message(BalState.waiting_user)
async def bal_get_user(message: Message, state: FSMContext):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    text = message.text.strip().lstrip("@")
    import aiosqlite
    from config import DB_FILE
    target = None
    async with aiosqlite.connect(DB_FILE) as conn:
        if text.lstrip("-").isdigit():
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
        target = {"user_id": row[0], "full_name": row[1]}

    if not target:
        await message.answer("❌ Topilmadi. Qaytadan kiriting yoki /cancel")
        return

    data = await state.get_data()
    action = data.get("action")
    await state.update_data(target_id=target["user_id"], target_name=target["full_name"])
    await state.set_state(BalState.waiting_amount)

    ref_count = await db.get_referral_count(target["user_id"])
    action_text = "qo'shmoqchisiz" if action == "bal:add" else "ayirmoqchisiz"
    await message.answer(
        f"👤 <b>{target['full_name']}</b>\n"
        f"💰 Hozirgi bali: <b>{ref_count} ta</b>\n\n"
        f"Nechta bal {action_text}?\n"
        f"Raqam yuboring:",
        parse_mode="HTML"
    )


@router.message(BalState.waiting_amount)
async def bal_apply(message: Message, state: FSMContext, bot: Bot):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    amount = int(message.text.strip())
    data = await state.get_data()
    action = data.get("action")
    target_id = data.get("target_id")
    target_name = data.get("target_name")
    await state.clear()

    import aiosqlite
    from config import DB_FILE

    if action == "bal:add":
        # Soxta referral qo'shamiz (admin ID dan)
        async with aiosqlite.connect(DB_FILE) as conn:
            for i in range(amount):
                try:
                    fake_id = -(target_id * 1000 + i)
                    await conn.execute(
                        "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                        (target_id, fake_id)
                    )
                except Exception:
                    pass
            await conn.commit()
        action_text = f"+{amount} ta bal qo'shildi"
    else:
        # Referrallardan ayiramiz
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute(
                "SELECT id FROM referrals WHERE referrer_id=? LIMIT ?",
                (target_id, amount)
            ) as c:
                rows = await c.fetchall()
            for row in rows:
                await conn.execute("DELETE FROM referrals WHERE id=?", (row[0],))
            await conn.commit()
        action_text = f"-{amount} ta bal ayirildi"

    new_count = await db.get_referral_count(target_id)
    await message.answer(
        f"✅ <b>{target_name}</b>\n"
        f"{action_text}\n"
        f"💰 Yangi bali: <b>{new_count} ta</b>",
        parse_mode="HTML"
    )


# ─── /setbal BUYRUQ ──────────────────────────────────────────

class SetBalState(StatesGroup):
    waiting_amount = State()


@router.message(F.text.startswith("/setbal"))
async def setbal_cmd(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer(
            "❌ To'g'ri format:\n"
            "<code>/setbal @username</code>\n"
            "<code>/setbal 123456789</code>",
            parse_mode="HTML"
        )
        return

    text = parts[1].lstrip("@")
    import aiosqlite
    from config import DB_FILE

    target = None
    async with aiosqlite.connect(DB_FILE) as conn:
        if text.isdigit():
            async with conn.execute(
                "SELECT user_id, full_name, username FROM users WHERE user_id=?", (int(text),)
            ) as c:
                row = await c.fetchone()
        else:
            async with conn.execute(
                "SELECT user_id, full_name, username FROM users WHERE username=?", (text,)
            ) as c:
                row = await c.fetchone()

    if row:
        target = {"user_id": row[0], "full_name": row[1], "username": row[2]}

    if not target:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    ref_count = await db.get_referral_count(target["user_id"])
    rank = await db.get_user_rank(target["user_id"])
    uname = f"@{target['username']}" if target["username"] else "username yo'q"

    await state.set_state(SetBalState.waiting_amount)
    await state.update_data(
        target_id=target["user_id"],
        target_name=target["full_name"],
        old_bal=ref_count
    )

    await message.answer(
        f"👤 <b>{target['full_name']}</b> ({uname})\n"
        f"🆔 <code>{target['user_id']}</code>\n"
        f"💰 Hozirgi bali: <b>{ref_count} ta</b>\n"
        f"🏆 O'rni: <b>{rank}-o'rin</b>\n\n"
        f"Yangi balini kiriting (faqat raqam):\n"
        f"Bekor qilish: /cancel",
        parse_mode="HTML"
    )


@router.message(SetBalState.waiting_amount)
async def setbal_amount(message: Message, state: FSMContext):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    new_bal = int(message.text.strip())
    data = await state.get_data()
    target_id = data["target_id"]
    target_name = data["target_name"]
    old_bal = data["old_bal"]

    await state.update_data(new_bal=new_bal)

    diff = new_bal - old_bal
    diff_text = f"+{diff}" if diff >= 0 else str(diff)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"setbal:confirm:{target_id}:{new_bal}")
    kb.button(text="❌ Bekor", callback_data="setbal:cancel")
    kb.adjust(2)

    await message.answer(
        f"⚠️ <b>Tasdiqlaysizmi?</b>\n\n"
        f"👤 {target_name}\n"
        f"💰 Eski bal: <b>{old_bal}</b>\n"
        f"💰 Yangi bal: <b>{new_bal}</b>\n"
        f"📊 O'zgarish: <b>{diff_text}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await state.clear()


@router.callback_query(F.data.startswith("setbal:confirm:"))
async def setbal_confirm(callback: CallbackQuery):
    parts = callback.data.split(":")
    target_id = int(parts[2])
    new_bal = int(parts[3])

    import aiosqlite
    from config import DB_FILE

    async with aiosqlite.connect(DB_FILE) as conn:
        # Avval bu odamning barcha referrallarini o'chirish
        await conn.execute("DELETE FROM referrals WHERE referrer_id=?", (target_id,))
        # Yangi bal qo'shish (soxta referrallar bilan)
        for i in range(new_bal):
            fake_id = -(target_id * 10000 + i)
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                    (target_id, fake_id)
                )
            except Exception:
                pass
        await conn.commit()

    actual = await db.get_referral_count(target_id)
    rank = await db.get_user_rank(target_id)

    await callback.message.edit_text(
        f"✅ <b>Bal yangilandi!</b>\n\n"
        f"💰 Yangi bal: <b>{actual} ta</b>\n"
        f"🏆 Yangi o'rni: <b>{rank}-o'rin</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "setbal:cancel")
async def setbal_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Bekor qilindi.")


# ─── RETENTION ───────────────────────────────────────────────

@router.message(F.text.startswith("/retention"))
async def retention_cmd(message: Message, bot: Bot):
    parts = message.text.strip().split()
    import aiosqlite
    from config import DB_FILE
    from datetime import timedelta

    # Umumiy yoki shaxsiy
    if len(parts) == 1:
        # Umumiy statistika
        async with aiosqlite.connect(DB_FILE) as conn:
            # So'nggi 7 kunda qo'shilganlar
            async with conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE joined_at >= datetime('now', '-7 days')
            """) as c:
                total_joined = (await c.fetchone())[0]

            # Hali guruhda bormi tekshirish
            async with conn.execute("""
                SELECT user_id FROM users 
                WHERE joined_at >= datetime('now', '-7 days')
                AND is_member = 1
            """) as c:
                members = await c.fetchall()

        still_in = 0
        for (uid,) in members:
            try:
                m = await bot.get_chat_member(GROUP_ID, uid)
                if m.status not in ('left', 'kicked', 'banned'):
                    still_in += 1
                else:
                    async with aiosqlite.connect(DB_FILE) as conn:
                        await conn.execute(
                            "UPDATE users SET is_member=0 WHERE user_id=?", (uid,)
                        )
                        await conn.commit()
            except Exception:
                pass

        left = total_joined - still_in
        percent = round(still_in / total_joined * 100) if total_joined > 0 else 0

        await message.answer(
            f"📊 <b>A'zolar saqlanishi (so'nggi 7 kun)</b>\n\n"
            f"➕ Qo'shildi: <b>{total_joined} ta</b>\n"
            f"❌ Chiqib ketdi: <b>{left} ta</b>\n"
            f"✅ Qoldi: <b>{still_in} ta</b>\n\n"
            f"📈 Saqlanish: <b>{percent}%</b>\n\n"
            f"💡 Shaxsiy tekshirish:\n"
            f"<code>/retention @username</code>\n"
            f"<code>/retention 123456789</code>",
            parse_mode='HTML'
        )

    else:
        # Shaxsiy — aynan bir kishi qo'shganlari
        text = parts[1].lstrip('@')

        async with aiosqlite.connect(DB_FILE) as conn:
            if text.isdigit():
                async with conn.execute(
                    "SELECT user_id, full_name, username FROM users WHERE user_id=?", (int(text),)
                ) as c:
                    row = await c.fetchone()
            else:
                async with conn.execute(
                    "SELECT user_id, full_name, username FROM users WHERE username=?", (text,)
                ) as c:
                    row = await c.fetchone()

        if not row:
            await message.answer("❌ Foydalanuvchi topilmadi.")
            return

        target_id, full_name, username = row

        # Bu odam qo'shgan barcha odamlar
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("""
                SELECT r.referred_id FROM referrals r
                WHERE r.referrer_id = ?
            """, (target_id,)) as c:
                referred = await c.fetchall()

        total = len(referred)
        still_in = 0
        left_count = 0

        for (uid,) in referred:
            try:
                m = await bot.get_chat_member(GROUP_ID, uid)
                if m.status not in ('left', 'kicked', 'banned'):
                    still_in += 1
                else:
                    left_count += 1
                    async with aiosqlite.connect(DB_FILE) as conn:
                        await conn.execute(
                            "UPDATE users SET is_member=0 WHERE user_id=?", (uid,)
                        )
                        await conn.commit()
            except Exception:
                left_count += 1

        percent = round(still_in / total * 100) if total > 0 else 0
        uname = f"@{username}" if username else f"ID: {target_id}"

        emoji = "🟢" if percent >= 70 else "🟡" if percent >= 40 else "🔴"

        result_txt = "🟢 Yaxshi natija!" if percent >= 70 else ("🟡 Ortacha" if percent >= 40 else "🔴 Past - nakrutka bolishi mumkin!")
        await message.answer(
            f"📊 <b>{full_name}</b> ({uname}) qoshganlari:\n\n"
            f"➕ Jami qoshdi: <b>{total} ta</b>\n"
            f"❌ Chiqib ketdi: <b>{left_count} ta</b>\n"
            f"✅ Hali guruhda: <b>{still_in} ta</b>\n\n"
            f"{emoji} Saqlanish: <b>{percent}%</b>\n\n"
            f"{result_txt}",
            parse_mode='HTML'
        )


# ─── BAL SO'RASH — ADMIN TASDIQLASH ─────────────────────────

@router.callback_query(F.data.startswith("reqadmin:"))
async def admin_request_action(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    action = parts[1]
    token = parts[2]
    to_id = int(parts[3])
    from_id = int(parts[4])
    bal = int(parts[5]) if len(parts) > 5 else 0

    import aiosqlite
    from config import DB_FILE

    if action == "approve":
        # O'tkazish
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.execute("DELETE FROM referrals WHERE referrer_id=?", (from_id,))
            for i in range(bal):
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
        new_count = await db.get_referral_count(to_id)

        to_user = await db.get_user(to_id)
        to_name = to_user['full_name'] if to_user else str(to_id)

        await callback.message.edit_text(
            f"✅ <b>Tasdiqlandi!</b>\n"
            f"💰 {bal} ta bal → {to_name}\n"
            f"Yangi bali: {new_count} ta"
        )

        try:
            await bot.send_message(
                to_id,
                f"🎉 Admin tasdiqladi!\n"
                f"💰 <b>{bal} ta bal</b> sizga o'tkazildi!\n"
                f"Endi sizda <b>{new_count} ta</b> ball bor. 🏆",
                parse_mode='HTML'
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                from_id,
                f"✅ Admin tasdiqladi — balingiz o'tkazildi.",
            )
        except Exception:
            pass

    elif action == "reject":
        await db.update_bal_request_status(token, 'rejected')
        await callback.message.edit_text("❌ Transfer bekor qilindi.")

        try:
            await bot.send_message(from_id, "❌ Admin transfer so'rovingizni rad etdi.")
        except Exception:
            pass
        try:
            await bot.send_message(to_id, "❌ Transfer admin tomonidan rad etildi.")
        except Exception:
            pass

    elif action == "ban":
        await db.blacklist_user(to_id, True)
        await db.blacklist_user(from_id, True)
        await db.update_bal_request_status(token, 'banned')

        await callback.message.edit_text(
            f"🚫 Ikkalasi ban qilindi!\n"
            f"ID 1: <code>{from_id}</code>\n"
            f"ID 2: <code>{to_id}</code>",
            parse_mode='HTML'
        )

        for uid in [from_id, to_id]:
            try:
                await bot.send_message(uid, "🚫 Siz konkursdan mahrum etildingiz.")
            except Exception:
                pass