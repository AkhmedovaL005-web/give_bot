import logging
from aiogram import Router, Bot, F
from aiogram.types import Message

import database as db
from config import ADMIN_IDS
from utils import user_mention

logger = logging.getLogger(__name__)
router = Router()

MENU_BUTTONS = [
    "🔗 Linkimni olish",
    "👥 Achkolarim", 
    "🎁 Bal berish",
    "📞 Admin bilan bog'lanish",
    "🚀 Give Away boshlash",
    "⛔ Tugatish",
    "📢 Reklama",
    "📈 Admin statistika",
    "🏆 G'oliblar",
    "💾 Backup olish",
    "🚫 Ban",
]


@router.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: Message):
    await db.set_support_mode(message.from_user.id, True)
    await message.answer(
        "✍️ Adminga yozmoqchi bo'lgan xabaringizni yuboring.\n"
        "Bekor qilish: /cancel"
    )


@router.message(F.text == "/cancel")
async def cancel_support(message: Message):
    await db.set_support_mode(message.from_user.id, False)
    await message.answer("❌ Bekor qilindi.")


@router.message(F.from_user.func(lambda u: u.id not in ADMIN_IDS))
async def forward_to_admin(message: Message, bot: Bot):
    if not message.text:
        return

    # Tugma bosgan bo'lsa — support emas
    if message.text in MENU_BUTTONS or message.text.startswith('/'):
        return

    user_id = message.from_user.id
    in_support = await db.get_support_mode(user_id)
    if not in_support:
        return

    await db.set_support_mode(user_id, False)

    user = message.from_user
    header = (
        f"📩 <b>Yangi xabar</b>\n"
        f"👤 {user_mention(user.full_name, user.id)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'@' + user.username if user.username else 'username yoq'}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{message.text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(admin_id, header, parse_mode='HTML')
            await db.save_ticket(user_id, message.message_id, sent.message_id, admin_id)
        except Exception as e:
            logger.error(f"Adminga yuborib bolmadi {admin_id}: {e}")

    await message.answer("✅ Xabaringiz adminga yetkazildi. Tez orada javob berishadi.")


@router.message(F.reply_to_message, F.from_user.func(lambda u: u.id in ADMIN_IDS))
async def admin_reply(message: Message, bot: Bot):
    replied = message.reply_to_message
    if not replied:
        return

    ticket = await db.get_ticket_by_admin_msg(replied.message_id)
    if not ticket:
        return

    user_id = ticket[0]
    try:
        await bot.send_message(
            user_id,
            f"👨‍💼 <b>Admin javobi:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
        await message.reply("✅ Javob foydalanuvchiga yetkazildi.")
    except Exception as e:
        await message.reply(f"❌ Yuborib bolmadi: {e}")
