# =============================================
#   SOZLAMALAR
# =============================================

import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "8758446528:AAHF1AahPEE4xtH3p_Dwz9x1gbA4XIiuvZU")

GROUP_ID = -1003371929345
CHANNEL_ID = -1001599134202        # @Azikwww2022 kanal
CHANNEL_URL = "https://t.me/Azikwww2022"
CHECK_CHANNEL = True   # kanal tekshiruvi yoqildi

ADMIN_IDS = [7201215484, 5845294124]

DB_FILE = "giveaway.db"
BOT_USERNAME = "give_mebot"

LEADERBOARD_HOURS = [6, 12, 18, 0]

BACKUP_HOUR = 23
BACKUP_MINUTE = 59

TOP_WINNERS_COUNT = 3
TOP_RANDOM_POOL_START = 4
TOP_RANDOM_POOL_END = 10
TOP_RANDOM_COUNT = 2
GLOBAL_RANDOM_COUNT = 1
MIN_REFERRALS_FOR_RANDOM = 10

MIN_ACCOUNT_AGE_DAYS = 30
SUSPICIOUS_REFERRAL_LIMIT = 50

TZ_OFFSET = 5
DAILY_GOAL = 5
BACKUP_WINNERS_COUNT = 3

# Google Sheets
GOOGLE_CREDENTIALS_FILE = "credentials.json"  # JSON kalit fayl nomi
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"   # Sheets URL dan oling
USE_GOOGLE_SHEETS = False  # credentials.json qo'shgandan keyin True qiling

# ─── ARXIV KANAL ─────────────────────────────────────────────
BACKUP_CHANNEL_ID = -1003704523254
BOT_NAME = "give_mebot"

# ─── ZIYO MEBEL ──────────────────────────────────────────────
ZIYO_MEBEL_GROUP_ID = -1002237829841
ZIYO_MEBEL_URL = "https://t.me/Binary_Mind_Uz"

# ─── GURUH HIMOYA ────────────────────────────────────────────
# Nechta odam qo'shgach yoza oladi (admin o'zgartiradi)
WRITE_LIMIT = 3
# Nechta odam qo'shgach link tashlay oladi
LINK_LIMIT = 20
# Link tashlagach yana nechta so'raladi (aldash)
LINK_EXTRA = 10

# ─── REKLAMA TARQATISH ───────────────────────────────────────
# Bot admin bo'lgan kanal va guruhlar
BROADCAST_CHATS = [
    -1003371929345,   # TO'RAQO'RG'ON guruhi
    -1001599134202,   # Asosiy kanal
    -1002237829841,   # Ziyo Mebel guruhi
]