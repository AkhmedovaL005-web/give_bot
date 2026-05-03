import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

import database as db
from config import (
    ADMIN_IDS, LEADERBOARD_HOURS, BACKUP_HOUR, BACKUP_MINUTE,
    TZ_OFFSET, MIN_REFERRALS_FOR_RANDOM
)
from utils import build_leaderboard_text, build_motivational_text, send_to_admins, time_remaining

logger = logging.getLogger(__name__)
TZ = f"Asia/Tashkent"


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TZ)

    # Leaderboard + motivatsiya — har 6 soatda (06, 12, 18, 00)
    for hour in LEADERBOARD_HOURS:
        scheduler.add_job(
            send_leaderboard_and_motivations,
            CronTrigger(hour=hour, minute=0, timezone=TZ),
            args=[bot],
            id=f"leaderboard_{hour}",
            replace_existing=True
        )

    # Kunlik backup — 23:59
    scheduler.add_job(
        send_daily_backup,
        CronTrigger(hour=BACKUP_HOUR, minute=BACKUP_MINUTE, timezone=TZ),
        args=[bot],
        id="daily_backup",
        replace_existing=True
    )

    # Give away tugash tekshiruvi — har daqiqada
    scheduler.add_job(
        check_giveaway_end,
        'interval',
        minutes=1,
        args=[bot],
        id="check_end",
        replace_existing=True
    )

    # 24 soat qolganda eslatma — har soatda tekshiriladi
    scheduler.add_job(
        check_24h_warning,
        'interval',
        hours=1,
        args=[bot],
        id="check_24h",
        replace_existing=True
    )

    return scheduler


async def send_leaderboard_and_motivations(bot: Bot):
    """Har 6 soatda: adminlarga leaderboard + foydalanuvchilarga motivatsiya"""
    gw = await db.get_giveaway()
    if not gw or not gw['is_active']:
        return

    # Leaderboard adminlarga
    rows = await db.get_leaderboard(10)
    lb_text = build_leaderboard_text(rows, show_counts=True)

    total_users = await db.get_total_users()
    total_refs = await db.get_total_referrals()
    today = await db.get_today_joins()

    ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
    time_left = time_remaining(ends)

    admin_text = (
        f"📊 <b>LEADERBOARD YANGILANDI</b>\n\n"
        f"{lb_text}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Jami: <b>{total_users}</b> | 🔗 Referrallar: <b>{total_refs}</b>\n"
        f"📅 Bugun: <b>{today}</b> | ⏰ Qoldi: <b>{time_left}</b>"
    )
    await send_to_admins(bot, admin_text, parse_mode='HTML')

    # Foydalanuvchilarga motivatsiya xabarlari
    all_users = await db.get_all_active_users()
    leaderboard = await db.get_leaderboard(10)
    lb_dict = {row[0]: row[3] for row in leaderboard}

    for user_id in all_users:
        try:
            u = await db.get_user(user_id)
            if not u:
                continue
            lang = u['lang'] if u['lang'] in ('uz', 'ru') else 'uz'
            rank = await db.get_user_rank(user_id)
            ref_count = await db.get_referral_count(user_id)

            if rank == 0 or ref_count == 0:
                continue

            # Nechi ball yetishmaydi
            if rank <= 3:
                # Keyingisi bilan farq
                next_rank_count = await db.get_rank_referral_count(rank + 1)
                needed = ref_count - next_rank_count + 1
            elif rank <= 10:
                # Top 3 ga kirish uchun
                top3_count = await db.get_rank_referral_count(3)
                needed = top3_count - ref_count + 1
            else:
                # Top 10 ga kirish uchun
                top10_count = await db.get_rank_referral_count(10)
                needed = top10_count - ref_count + 1

            if needed < 0:
                needed = 0

            text = build_motivational_text(rank, ref_count, needed, lang)
            await bot.send_message(user_id, text, parse_mode='HTML')
        except Exception:
            pass


async def check_giveaway_end(bot: Bot):
    """Give away tugash vaqtini tekshirish"""
    gw = await db.get_giveaway()
    if not gw or not gw['is_active'] or not gw['ends_at']:
        return

    ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    if now >= ends:
        logger.info("Give away vaqti tugadi — g'oliblar e'lon qilinmoqda")
        from handlers.admin import announce_winners
        await announce_winners(bot)


async def check_24h_warning(bot: Bot):
    """Tugashiga 24 soat qolganda ogohlantirish"""
    gw = await db.get_giveaway()
    if not gw or not gw['is_active'] or not gw['ends_at']:
        return

    ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = ends - now

    # 24 soat ± 30 daqiqa oralig'ida
    if timedelta(hours=23, minutes=30) <= diff <= timedelta(hours=24, minutes=30):
        all_users = await db.get_all_active_users()
        for user_id in all_users:
            try:
                u = await db.get_user(user_id)
                lang = u['lang'] if u and u['lang'] in ('uz', 'ru') else 'uz'
                ref_count = await db.get_referral_count(user_id)
                need_random = max(0, MIN_REFERRALS_FOR_RANDOM - ref_count)

                random_txt = "✅ Random sovga uchun huquqingiz bor!" if need_random == 0 else f"🎲 Random sovgaga yana {need_random} ta odam kerak!"
                text = (
                    "⏰ <b>ESLATMA!</b>\n\n"
                    f"Give Away tugashiga <b>24 soat</b> qoldi!\n"
                    f"Sizda hozir <b>{ref_count} ta</b> ball bor.\n\n"
                    f"{random_txt}\n\n"
                    "🔗 Linkingizni oling va tarqating: /mylink\n"
                    "⚡ Oxirgi imkoniyat!"
                )
                await bot.send_message(user_id, text, parse_mode='HTML')
            except Exception:
                pass


async def send_daily_backup(bot: Bot):
    """Har kuni 23:59 da backup yuborish"""
    from handlers.admin import send_backup
    await send_backup(bot)
    logger.info("Kunlik backup yuborildi")