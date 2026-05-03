import logging
from datetime import datetime, timezone
from aiogram import Router, Bot, F
from aiogram.types import ChatMemberUpdated

import database as db
from config import GROUP_ID, ADMIN_IDS, SUSPICIOUS_REFERRAL_LIMIT
from utils import send_to_admins, user_mention

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member(F.chat.id == GROUP_ID)
async def on_chat_member(event: ChatMemberUpdated, bot: Bot):
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    user = event.new_chat_member.user
    if user.is_bot:
        return

    if new_status in ('member', 'administrator') and old_status in ('left', 'kicked', 'restricted', 'banned'):
        await handle_join(event, bot)


async def handle_join(event: ChatMemberUpdated, bot: Bot):
    user = event.new_chat_member.user

    # Yangi foydalanuvchini DBga qo'shish
    await db.register_user(user.id, user.username, user.full_name)

    referrer_id = None

    # 1-usul: Bot linki orqali
    if event.invite_link and event.invite_link.invite_link:
        link = event.invite_link.invite_link
        referrer_id = await db.get_user_id_by_link(link)

    # 2-usul: Kim qo'shdi (added_by) — admin bo'lmasa ball beriladi
    if not referrer_id and event.from_user:
        adder_id = event.from_user.id
        if adder_id not in ADMIN_IDS and adder_id != user.id:
            referrer_id = adder_id

    if not referrer_id or referrer_id == user.id:
        return

    if await db.is_blacklisted(referrer_id):
        return

    # Referrer DBda yo'q bo'lsa — guruhdan olib qo'shamiz
    referrer = await db.get_user(referrer_id)
    if not referrer:
        try:
            chat_member = await bot.get_chat_member(GROUP_ID, referrer_id)
            ref_user = chat_member.user
            await db.register_user(ref_user.id, ref_user.username, ref_user.full_name)
        except Exception:
            await db.register_user(referrer_id, None, str(referrer_id))

    success = await db.add_referral(referrer_id, user.id)
    if success:
        ref_count = await db.get_referral_count(referrer_id)
        logger.info(f"Yangi referral: {referrer_id} -> {user.id} (jami: {ref_count})")

        # Shubhali faollik tekshiruvi
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour_count = await db.get_hourly_referrals(referrer_id, now.hour, date_str)

        if hour_count >= SUSPICIOUS_REFERRAL_LIMIT:
            ref_user = await db.get_user(referrer_id)
            name = ref_user['full_name'] if ref_user else str(referrer_id)
            await send_to_admins(
                bot,
                f"⚠️ <b>SHUBHALI FAOLLIK!</b>\n\n"
                f"Foydalanuvchi: {user_mention(name, referrer_id)}\n"
                f"1 soatda <b>{hour_count} ta</b> odam qo'shdi!\n\n"
                f"Tekshirish tavsiya etiladi.",
                parse_mode='HTML'
            )
