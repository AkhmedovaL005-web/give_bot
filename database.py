import aiosqlite
import logging
from datetime import datetime
from config import DB_FILE

logger = logging.getLogger(__name__)


async def init_db():
    import os
    _db_dir = os.path.dirname(DB_FILE)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                full_name       TEXT,
                lang            TEXT DEFAULT 'uz',
                joined_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_member       INTEGER DEFAULT 1,
                started_bot     INTEGER DEFAULT 1,
                bot_blocked     INTEGER DEFAULT 0,
                transfer_done   INTEGER DEFAULT 0,
                blacklisted     INTEGER DEFAULT 0,
                link_sent_at    TIMESTAMP DEFAULT NULL,
                last_active     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backed_up       INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id     INTEGER NOT NULL,
                referred_id     INTEGER NOT NULL UNIQUE,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                user_id         INTEGER PRIMARY KEY,
                link            TEXT NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                is_active       INTEGER DEFAULT 0,
                started_at      TIMESTAMP DEFAULT NULL,
                ends_at         TIMESTAMP DEFAULT NULL,
                finished        INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS winners (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                prize_type      TEXT NOT NULL,
                rank            INTEGER DEFAULT NULL,
                announced_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup          INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_msg (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                message_id      INTEGER DEFAULT NULL,
                chat_id         INTEGER DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                message_id      INTEGER NOT NULL,
                admin_msg_id    INTEGER DEFAULT NULL,
                answered        INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                hour            INTEGER NOT NULL,
                count           INTEGER DEFAULT 0,
                date            TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bal_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id     INTEGER NOT NULL,
                token       TEXT NOT NULL UNIQUE,
                status      TEXT DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: backed_up ustuni qo'shish (eski DB lar uchun)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN backed_up INTEGER DEFAULT 0")
        except Exception:
            pass  # Ustun allaqachon bor
        await db.execute("INSERT OR IGNORE INTO giveaway (id) VALUES (1)")
        await db.execute("INSERT OR IGNORE INTO leaderboard_msg (id) VALUES (1)")
        await db.commit()
    logger.info("✅ Database tayyor")






# ─── FOYDALANUVCHI ───────────────────────────────────────────

async def register_user(user_id: int, username: str, full_name: str, lang: str = 'uz') -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)) as c:
            exists = await c.fetchone()
        if exists:
            await db.execute(
                "UPDATE users SET username=?,full_name=?,bot_blocked=0,last_active=? WHERE user_id=?",
                (username, full_name, datetime.utcnow(), user_id)
            )
            await db.commit()
            return False
        await db.execute(
            "INSERT INTO users (user_id,username,full_name,lang) VALUES (?,?,?,?)",
            (user_id, username, full_name, lang)
        )
        await db.commit()

        # Google Sheets ga ham yozish
        try:
            from config import USE_GOOGLE_SHEETS
            if USE_GOOGLE_SHEETS:
                from sheets import save_user_to_sheets
                await save_user_to_sheets(user_id, full_name, username)
        except Exception:
            pass

        return True


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            return await c.fetchone()


async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        await db.commit()


async def set_bot_blocked(user_id: int, blocked: bool):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("UPDATE users SET bot_blocked=? WHERE user_id=?", (int(blocked), user_id))
        await db.commit()


async def set_link_sent(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("UPDATE users SET link_sent_at=? WHERE user_id=?", (datetime.utcnow(), user_id))
        await db.commit()


async def get_all_active_users():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE bot_blocked=0 AND blacklisted=0"
        ) as c:
            rows = await c.fetchall()
    return [r[0] for r in rows]


async def blacklist_user(user_id: int, blacklisted: bool):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("UPDATE users SET blacklisted=? WHERE user_id=?", (int(blacklisted), user_id))
        await db.commit()


async def is_blacklisted(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT blacklisted FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
    return bool(row[0]) if row else False


# ─── REFERRAL ────────────────────────────────────────────────

async def add_referral(referrer_id: int, referred_id: int) -> bool:
    """Referral qo'shish. True = muvaffaqiyatli"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT id FROM referrals WHERE referred_id=?", (referred_id,)) as c:
            if await c.fetchone():
                return False
        try:
            await db.execute(
                "INSERT INTO referrals (referrer_id,referred_id) VALUES (?,?)",
                (referrer_id, referred_id)
            )
            now = datetime.utcnow()
            date_str = now.strftime("%Y-%m-%d")
            hour = now.hour
            await db.execute("""
                INSERT INTO daily_referrals (user_id,hour,count,date) VALUES (?,?,1,?)
                ON CONFLICT DO UPDATE SET count=count+1
            """, (referrer_id, hour, date_str))
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Referral xatosi: {e}")
            return False


async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else 0


async def get_referrals_list(user_id: int, offset: int = 0, limit: int = 50):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.full_name, u.username, r.created_at
            FROM referrals r
            JOIN users u ON u.user_id = r.referred_id
            WHERE r.referrer_id=?
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset)) as c:
            return await c.fetchall()


async def get_hourly_referrals(user_id: int, hour: int, date_str: str) -> int:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT count FROM daily_referrals WHERE user_id=? AND hour=? AND date=?",
            (user_id, hour, date_str)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else 0


# ─── INVITE LINK ─────────────────────────────────────────────

async def save_invite_link(user_id: int, link: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR REPLACE INTO invite_links (user_id,link) VALUES (?,?)",
            (user_id, link)
        )
        await db.commit()


async def get_invite_link(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT link FROM invite_links WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
    return row[0] if row else None


async def get_user_id_by_link(link: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT user_id FROM invite_links WHERE link=?", (link,)) as c:
            row = await c.fetchone()
    return row[0] if row else None


# ─── LEADERBOARD ─────────────────────────────────────────────

async def get_leaderboard(limit: int = 10):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name, COUNT(r.id) as cnt
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            WHERE u.blacklisted=0
            GROUP BY u.user_id
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit,)) as c:
            return await c.fetchall()


async def get_user_rank(user_id: int) -> int:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT ranked.rnk FROM (
                SELECT user_id, RANK() OVER (ORDER BY COUNT(r.id) DESC) as rnk
                FROM users u
                LEFT JOIN referrals r ON r.referrer_id=u.user_id
                WHERE u.blacklisted=0
                GROUP BY u.user_id
            ) ranked WHERE ranked.user_id=?
        """, (user_id,)) as c:
            row = await c.fetchone()
    return row[0] if row else 0


async def get_rank_referral_count(rank: int) -> int:
    """Berilgan o'rindagi odamning referral soni"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT COUNT(r.id) as cnt
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            WHERE u.blacklisted=0
            GROUP BY u.user_id
            ORDER BY cnt DESC
            LIMIT 1 OFFSET ?
        """, (rank - 1,)) as c:
            row = await c.fetchone()
    return row[0] if row else 0


# ─── BAL TRANSFER ────────────────────────────────────────────

async def transfer_points(from_id: int, to_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT transfer_done FROM users WHERE user_id=?", (from_id,)) as c:
            row = await c.fetchone()
        if not row or row[0]:
            return False
        await db.execute("""
            UPDATE referrals SET referrer_id=? WHERE referrer_id=?
        """, (to_id, from_id))
        await db.execute("UPDATE users SET transfer_done=1 WHERE user_id=?", (from_id,))
        await db.commit()
        return True


# ─── GIVE AWAY ───────────────────────────────────────────────

async def get_giveaway():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM giveaway WHERE id=1") as c:
            return await c.fetchone()


async def start_giveaway(started_at: datetime, ends_at: datetime):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "UPDATE giveaway SET is_active=1,started_at=?,ends_at=?,finished=0 WHERE id=1",
            (started_at, ends_at)
        )
        await db.commit()


async def finish_giveaway():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("UPDATE giveaway SET is_active=0,finished=1 WHERE id=1")
        await db.commit()


# ─── G'OLIBLAR ───────────────────────────────────────────────

async def get_top_winners(count: int = 3):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name, COUNT(r.id) as cnt
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            WHERE u.blacklisted=0
            GROUP BY u.user_id
            HAVING cnt > 0
            ORDER BY cnt DESC
            LIMIT ?
        """, (count,)) as c:
            return await c.fetchall()


async def get_random_pool_winners(start_rank: int, end_rank: int, count: int, exclude_ids: list):
    import random
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name, COUNT(r.id) as cnt
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            WHERE u.blacklisted=0
            GROUP BY u.user_id
            ORDER BY cnt DESC
            LIMIT ? OFFSET ?
        """, (end_rank - start_rank + 1, start_rank - 1)) as c:
            pool = await c.fetchall()
    pool = [p for p in pool if p[0] not in exclude_ids]
    return random.sample(pool, min(count, len(pool))) if pool else []


async def get_global_random_winner(exclude_ids: list, min_referrals: int):
    import random
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name, COUNT(r.id) as cnt
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            WHERE u.blacklisted=0
              AND u.started_bot=1
              AND u.bot_blocked=0
              AND u.is_member=1
            GROUP BY u.user_id
            HAVING cnt >= ?
        """, (min_referrals,)) as c:
            pool = await c.fetchall()
    pool = [p for p in pool if p[0] not in exclude_ids]
    return random.choice(pool) if pool else None


async def save_winner(user_id: int, prize_type: str, rank: int = None, backup: bool = False):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT INTO winners (user_id,prize_type,rank,backup) VALUES (?,?,?,?)",
            (user_id, prize_type, rank, int(backup))
        )
        await db.commit()


async def get_winners(backup: bool = False):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT w.user_id, w.prize_type, w.rank, u.username, u.full_name
            FROM winners w JOIN users u ON u.user_id=w.user_id
            WHERE w.backup=?
            ORDER BY w.rank ASC NULLS LAST, w.id ASC
        """, (int(backup),)) as c:
            return await c.fetchall()


async def get_already_won_ids():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT user_id FROM winners WHERE backup=0") as c:
            rows = await c.fetchall()
    return [r[0] for r in rows]


# ─── SUPPORT ─────────────────────────────────────────────────

async def save_ticket(user_id: int, message_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT INTO support_tickets (user_id,message_id) VALUES (?,?)",
            (user_id, message_id)
        )
        await db.commit()


async def get_ticket_by_admin_msg(admin_msg_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT user_id FROM support_tickets WHERE admin_msg_id=?", (admin_msg_id,)
        ) as c:
            return await c.fetchone()


async def update_ticket_admin_msg(user_id: int, message_id: int, admin_msg_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "UPDATE support_tickets SET admin_msg_id=?,answered=1 WHERE user_id=? AND message_id=?",
            (admin_msg_id, user_id, message_id)
        )
        await db.commit()


# ─── STATISTIKA ──────────────────────────────────────────────

async def get_total_users() -> int:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            return (await c.fetchone())[0]


async def get_total_referrals() -> int:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT COUNT(*) FROM referrals") as c:
            return (await c.fetchone())[0]


async def get_today_joins() -> int:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(joined_at)=?", (today,)
        ) as c:
            return (await c.fetchone())[0]


# ─── EXPORT ──────────────────────────────────────────────────

async def export_all_data():
    """CSV uchun barcha ma'lumotlarni qaytaradi"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name, u.lang,
                   u.joined_at, u.is_member, u.bot_blocked, u.blacklisted,
                   COUNT(r.id) as referrals
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id=u.user_id
            GROUP BY u.user_id
            ORDER BY referrals DESC
        """) as c:
            users = await c.fetchall()
        async with db.execute("""
            SELECT r.referrer_id, r.referred_id, r.created_at,
                   u1.full_name as referrer_name, u2.full_name as referred_name
            FROM referrals r
            JOIN users u1 ON u1.user_id=r.referrer_id
            JOIN users u2 ON u2.user_id=r.referred_id
        """) as c:
            referrals = await c.fetchall()
    return users, referrals


# ─── SUPPORT MODE ────────────────────────────────────────────

async def set_support_mode(user_id: int, mode: bool):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "UPDATE users SET lang=? WHERE user_id=?",
            ('support' if mode else 'uz', user_id)
        )
        await db.commit()


async def get_support_mode(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT lang FROM users WHERE user_id=?", (user_id,)
        ) as c:
            row = await c.fetchone()
    return row and row[0] == 'support'


async def save_ticket(user_id: int, message_id: int, admin_msg_id: int, admin_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR REPLACE INTO support_tickets (user_id, message_id, admin_msg_id) VALUES (?,?,?)",
            (user_id, message_id, admin_msg_id)
        )
        await db.commit()


async def revoke_all_invite_links(bot, group_id: int):
    """Give away tugagach barcha invite linklarni o'chirish"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT user_id, link FROM invite_links") as c:
            links = await c.fetchall()
    for user_id, link in links:
        try:
            await bot.revoke_chat_invite_link(group_id, link)
        except Exception:
            pass
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("DELETE FROM invite_links")
        await db.commit()


# ─── BAL SO'RASH ─────────────────────────────────────────────

async def create_request_table():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bal_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id     INTEGER NOT NULL,
                token       TEXT NOT NULL UNIQUE,
                status      TEXT DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def create_bal_request(from_id: int, token: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT INTO bal_requests (from_id, token) VALUES (?, ?)",
            (from_id, token)
        )
        await db.commit()


async def get_bal_request(token: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT id, from_id, status FROM bal_requests WHERE token=?", (token,)
        ) as c:
            return await c.fetchone()


async def update_bal_request_status(token: str, status: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "UPDATE bal_requests SET status=? WHERE token=?", (status, token)
        )
        await db.commit()


# ─── GURUH HIMOYA ────────────────────────────────────────────

async def init_guard_tables():
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        # Kalit so'zlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                word    TEXT NOT NULL UNIQUE
            )
        """)
        # Guruh sozlamalari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guard_settings (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            )
        """)
        # Foydalanuvchi link limiti
        await db.execute("""
            CREATE TABLE IF NOT EXISTS link_warned (
                user_id     INTEGER PRIMARY KEY,
                extra_done  INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def get_guard_setting(key: str, default: str) -> str:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT value FROM guard_settings WHERE key=?", (key,)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else default


async def set_guard_setting(key: str, value: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR REPLACE INTO guard_settings (key, value) VALUES (?,?)",
            (key, value)
        )
        await db.commit()


async def get_keywords() -> list:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute("SELECT word FROM keywords") as c:
            rows = await c.fetchall()
    return [r[0].lower() for r in rows]


async def add_keyword(word: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR IGNORE INTO keywords (word) VALUES (?)", (word.lower(),)
        )
        await db.commit()


async def remove_keyword(word: str):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("DELETE FROM keywords WHERE word=?", (word.lower(),))
        await db.commit()


async def is_link_warned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT extra_done FROM link_warned WHERE user_id=?", (user_id,)
        ) as c:
            row = await c.fetchone()
    return bool(row and row[0])


async def set_link_warned(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR REPLACE INTO link_warned (user_id, extra_done) VALUES (?,1)",
            (user_id,)
        )
        await db.commit()


async def backup_user_to_channel(bot, user_id: int, full_name: str, username: str, bot_name: str, channel_id: int):
    try:
        uname = f"@{username}" if username else "username yoq"
        await bot.send_message(
            channel_id,
            f"ID:{user_id} | {uname} | {full_name} | {bot_name}"
        )
    except Exception:
        pass


async def is_user_backed_up(user_id: int) -> bool:
    """Foydalanuvchi arxiv kanalga yozilganmi"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT 1 FROM users WHERE user_id=? AND backed_up=1", (user_id,)
        ) as c:
            return bool(await c.fetchone())


async def mark_user_backed_up(user_id: int):
    """Foydalanuvchini arxiv kanalga yozilgan deb belgilash"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "UPDATE users SET backed_up=1 WHERE user_id=?", (user_id,)
        )
        await db.commit()

# ─── GURUH VIP ADMINLARI ─────────────────────────────────────

async def init_group_admin_table():
    """Guruh adminlari jadvalini yaratish"""
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_admins (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def add_group_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "INSERT OR IGNORE INTO group_admins (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def remove_group_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        await db.execute(
            "DELETE FROM group_admins WHERE user_id=?", (user_id,)
        )
        await db.commit()


async def is_group_admin_vip(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT 1 FROM group_admins WHERE user_id=?", (user_id,)
        ) as c:
            return bool(await c.fetchone())


async def get_group_admins() -> list:
    async with aiosqlite.connect(DB_FILE, timeout=30) as db:
        async with db.execute(
            "SELECT user_id FROM group_admins ORDER BY added_at"
        ) as c:
            rows = await c.fetchall()
            return [r[0] for r in rows]