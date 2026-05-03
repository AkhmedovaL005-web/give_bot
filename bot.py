import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, init_guard_tables, init_group_admin_table
from scheduler import setup_scheduler
from handlers import user, admin, member, support, group_guard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    # Foydalanuvchi buyruqlari
    user_commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="mylink", description="Shaxsiy invite linkni olish"),
        BotCommand(command="mystats", description="Mening statistikam"),
        BotCommand(command="myinvites", description="Men qo'shgan odamlar"),
        BotCommand(command="top", description="Top 10 leaderboard"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # Admin buyruqlari
    admin_commands = user_commands + [
        BotCommand(command="startgiveaway", description="Give away boshlash"),
        BotCommand(command="endgiveaway", description="Give awayni tugatish"),
        BotCommand(command="adminstats", description="Admin statistika"),
        BotCommand(command="winners", description="G'oliblar ro'yxati"),
        BotCommand(command="backup", description="Ma'lumotlar zaxirasi"),
        BotCommand(command="ban", description="Foydalanuvchini bloklash"),
        BotCommand(command="cancel", description="Bekor qilish"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception as e:
            logger.warning(f"Admin buyruqlari o'rnatilmadi {admin_id}: {e}")


async def main():
    # DB ni ishga tushirish
    await init_db()
    await init_guard_tables()
    await init_group_admin_table()

    # Google Sheets ga ulanish
    from config import USE_GOOGLE_SHEETS, GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID
    if USE_GOOGLE_SHEETS:
        from sheets import init_sheets
        init_sheets(GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Routerlarni qo'shish (tartib muhim!)
    dp.include_router(group_guard.router)  # guruh himoya AVVAL
    dp.include_router(admin.router)    # admin
    dp.include_router(member.router)   # guruh eventlari
    dp.include_router(user.router)     # foydalanuvchi
    dp.include_router(support.router)  # support oxirida

    # Scheduler ishga tushirish
    scheduler = setup_scheduler(bot)
    scheduler.start()

    # Buyruqlarni o'rnatish
    await set_commands(bot)

    logger.info("✅ Bot ishga tushdi — @give_mebot")

    try:
        await dp.start_polling(bot, allowed_updates=[
            "message",
            "callback_query",
            "chat_member",
            "my_chat_member",
            "message_reaction"
        ])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())