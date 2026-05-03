# 🎁 Give Away Bot — @give_mebot

**TO'RAQO'RG'ON _ NATYAJNOY** guruhi uchun professional give away boti.

---

## ⚙️ O'rnatish

### 1. Talablar
- Python 3.10+
- VPS yoki server (24/7 ishlash uchun)

### 2. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 3. config.py ni to'ldirish
```python
BOT_TOKEN = "..."        # @BotFather dan oling
GROUP_ID = -100...       # Guruh ID
CHANNEL_ID = -100...     # Kanal ID (agar kerak bo'lsa)
ADMIN_IDS = [720..., 584...]  # Admin ID lari
BOT_USERNAME = "give_mebot"
```

### 4. Guruh ID ni olish
1. @userinfobot ga guruhdan istalgan xabar forward qiling
2. "Forwarded from chat" qatoridagi ID ni oling (manfiy son)

### 5. Botni guruhga admin qilish
Guruhga bot qo'shing va quyidagi huquqlarni bering:
- ✅ Invite users via link (MUHIM — linklar yaratish uchun)
- ✅ Delete messages (ixtiyoriy)
- ✅ Pin messages (ixtiyoriy)

### 6. Botni ishga tushirish
```bash
python bot.py
```

### 7. 24/7 ishlash uchun (Linux VPS)
```bash
# systemd service yaratish
sudo nano /etc/systemd/system/giveaway_bot.service
```

```ini
[Unit]
Description=Give Away Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/giveaway_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable giveaway_bot
sudo systemctl start giveaway_bot
sudo systemctl status giveaway_bot
```

---

## 📋 Buyruqlar

### Foydalanuvchi
| Buyruq | Vazifa |
|--------|--------|
| `/start` | Ro'yxatdan o'tish |
| `/mylink` | Shaxsiy invite link |
| `/mystats` | Statistika |
| `/myinvites` | Achkolar ro'yxati |
| `/top` | Top 10 |

### Admin
| Buyruq | Vazifa |
|--------|--------|
| `/startgiveaway` | Give away boshlash |
| `/endgiveaway` | Tugatish |
| `/adminstats` | To'liq statistika |
| `/winners` | G'oliblar |
| `/backup` | CSV zaxira |
| `/ban` | Foydalanuvchi ban |

---

## 🏆 Sovrin tizimi

1. **Top 1-3** — eng ko'p odam qo'shganlar
2. **Top 4-10 dan 2 ta random** — o'rta guruhdan tasodifiy
3. **1 ta global random** — kamida 10 odam qo'shgan, bot ishlatgan, bloklamagan

---

## 📅 Avtomatik jadval

| Vaqt | Vazifa |
|------|--------|
| 06:00, 12:00, 18:00, 00:00 | Adminlarga leaderboard + motivatsiya |
| Tugashiga 24 soat qolganda | Barcha foydalanuvchilarga eslatma |
| 23:59 | Kunlik CSV backup |
| Har daqiqa | Tugash vaqtini tekshirish |

---

## 🔒 Himoya

- Account 30 kundan yosh bo'lsa ball berilmaydi
- 1 soatda 50+ referral bo'lsa adminlarga ogohlantirish
- Bal transferi faqat 1 marta
- Blacklist tizimi

---

## ❓ Muammo bo'lsa

1. Bot guruhda admin ekanligini tekshiring
2. `GROUP_ID` to'g'ri ekanligini tekshiring (manfiy son bo'lishi kerak)
3. Bot token to'g'ri ekanligini tekshiring
4. Loglarni ko'ring: `sudo journalctl -u giveaway_bot -f`
