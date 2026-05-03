import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from config import TZ_OFFSET, ADMIN_IDS, GROUP_ID, CHECK_CHANNEL, CHANNEL_ID

logger = logging.getLogger(__name__)

TZ = timezone(timedelta(hours=TZ_OFFSET))


def now_local() -> datetime:
    return datetime.now(TZ)


def utc_to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def format_dt(dt: datetime) -> str:
    local = utc_to_local(dt) if dt else None
    return local.strftime("%d.%m.%Y %H:%M") if local else "—"


def time_remaining(ends_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    diff = ends_at - now
    if diff.total_seconds() <= 0:
        return "Tugadi"
    days = diff.days
    hours, rem = divmod(diff.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} kun")
    if hours:
        parts.append(f"{hours} soat")
    if minutes and not days:
        parts.append(f"{minutes} daqiqa")
    return " ".join(parts) or "1 daqiqadan kam"


def user_mention(full_name: str, user_id: int) -> str:
    return f'<a href="tg://user?id={user_id}">{full_name}</a>'


async def check_membership(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(GROUP_ID, user_id)
        in_group = member.status not in ('left', 'kicked', 'banned')
        if not in_group:
            return False
        if CHECK_CHANNEL:
            ch_member = await bot.get_chat_member(CHANNEL_ID, user_id)
            in_channel = ch_member.status not in ('left', 'kicked', 'banned')
            return in_channel
        return True
    except Exception:
        return False


async def send_to_admins(bot: Bot, text: str, **kwargs):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except Exception as e:
            logger.warning(f"Adminga yuborib bo'lmadi {admin_id}: {e}")


def build_leaderboard_text(rows: list, lang: str = 'uz', show_counts: bool = False) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    if lang == 'uz':
        lines.append("🏆 <b>TOP 10 — Give Away</b>\n")
    else:
        lines.append("🏆 <b>ТОП 10 — Конкурс</b>\n")

    for i, row in enumerate(rows, 1):
        user_id, username, full_name, cnt = row
        medal = medals.get(i, f"{i}.")
        name = full_name or username or "Noma'lum"
        if show_counts:
            lines.append(f"{medal} {name} — {cnt} ta")
        else:
            lines.append(f"{medal} {name}")

    if not rows:
        lines.append("Hali hech kim yo'q" if lang == 'uz' else "Пока никого нет")
    return "\n".join(lines)


def build_motivational_text(rank: int, ref_count: int, needed: int, lang: str = 'uz') -> str:
    if lang == 'uz':
        if rank <= 3:
            return (
                f"⚠️ Siz <b>{rank}-o'rin</b>dadasiz!\n"
                f"O'rningizni saqlang — raqiblar {needed} ta orqada. Davom eting! 🔥"
            )
        elif rank <= 10:
            return (
                f"💪 Siz <b>{rank}-o'rin</b>dadasiz!\n"
                f"Top 3 ga kirish uchun atigi <b>{needed} ta</b> odam yetishmayapti. "
                f"Harakatlaning! 🎁"
            )
        else:
            return (
                f"🎯 Siz <b>{rank}-o'rin</b>dadasiz.\n"
                f"Top 10 ga kirish uchun <b>{needed} ta</b> odam kerak. "
                f"Siz ham g'olib bo'lishingiz mumkin! 🏆"
            )
    else:
        if rank <= 3:
            return (
                f"⚠️ Вы на <b>{rank} месте</b>!\n"
                f"Удержите позицию — соперники всего на {needed} чел. позади. Не останавливайтесь! 🔥"
            )
        elif rank <= 10:
            return (
                f"💪 Вы на <b>{rank} месте</b>!\n"
                f"До топ 3 не хватает всего <b>{needed} чел.</b> Вперёд! 🎁"
            )
        else:
            return (
                f"🎯 Вы на <b>{rank} месте</b>.\n"
                f"Для топ 10 нужно ещё <b>{needed} чел.</b> Вы тоже можете выиграть! 🏆"
            )


async def generate_csv(users_data, referrals_data) -> io.BytesIO:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["=== FOYDALANUVCHILAR ==="])
    writer.writerow(["ID", "Username", "Ism", "Til", "Qo'shilgan", "A'zo", "Bloklagan", "Blacklist", "Referrallar"])
    for row in users_data:
        writer.writerow(row)

    writer.writerow([])
    writer.writerow(["=== REFERRALLAR ==="])
    writer.writerow(["Taklif qilgan ID", "Qo'shilgan ID", "Vaqt", "Taklif qilgan ismi", "Qo'shilgan ismi"])
    for row in referrals_data:
        writer.writerow(row)

    return io.BytesIO(buf.getvalue().encode('utf-8-sig'))
