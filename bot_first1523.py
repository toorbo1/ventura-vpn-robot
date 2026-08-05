#!/usr/bin/env python3
"""
VenturaVPN Bot - SPECIAL VERSION for @first1523 only
This is a separate version with new features ONLY for test user
"""
import os, json, time, urllib.request, urllib.parse, urllib.error, threading, logging

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    try:
        TOKEN = open("/root/bot/token").read().strip()
    except Exception:
        TOKEN = ""
API = f"https://api.telegram.org/bot{TOKEN}"

DATA_DIR = "/var/lib/ventura"
os.makedirs(DATA_DIR, exist_ok=True)

# Test user ID
TEST_USER_ID = "5302383529"  # @first1523

# Storage
user_data = {}  # Simple in-memory storage

logging.basicConfig(level=logging.INFO)

def api(method, **params):
    params = {k: v for k, v in params.items() if v is not None}
    body = urllib.parse.urlencode(
        {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
    ).encode()
    try:
        with urllib.request.urlopen(f"{API}/{method}", data=body, timeout=75) as r:
            return json.load(r)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_sub_status(uid):
    """Get subscription status from panel API."""
    try:
        req = urllib.request.Request(
            f"http://150.241.66.53/api/payment/has_active?uid={uid}",
            headers={"Host": "panel.venturavpn.club"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except:
        return {"active": False, "has_sub": False, "expires": 0, "devices": [], "max_devices": 5, "cid": ""}

def format_subscription_end_date(expires_timestamp):
    """Format timestamp to Russian readable date."""
    if not expires_timestamp or expires_timestamp == 0:
        return "неизвестно"
    try:
        t = time.localtime(expires_timestamp)
        day = str(int(time.strftime('%d', t)))
        months_ru = {
            '01': 'января', '02': 'февраля', '03': 'марта',
            '04': 'апреля', '05': 'мая', '06': 'июня',
            '07': 'июля', '08': 'августа', '09': 'сентября',
            '10': 'октября', '11': 'ноября', '12': 'декабря'
        }
        month_num = time.strftime('%m', t)
        year = time.strftime('%Y', t)
        month_name = months_ru.get(month_num, 'месяца')
        return f"{day} {month_name} {year}"
    except:
        return "неизвестно"

def get_subscription_details(uid):
    """Get detailed subscription info."""
    status = get_sub_status(uid)
    if not status.get("has_sub") and not status.get("active"):
        return None

    expires = status.get("expires", 0)
    devices_count = len(status.get("devices", []))
    max_devices = status.get("max_devices", 5)

    return {
        "active": status.get("active", False),
        "has_sub": status.get("has_sub", False),
        "expires": expires,
        "end_date_str": format_subscription_end_date(expires),
        "devices_used": devices_count,
        "max_devices": max_devices,
        "days_left": max(0, (expires - int(time.time())) // 86400) if expires else 0
    }

# Messages
WELCOME_NO_SUB = """Привееет! Каролина на связи ✨

Скажи «нет» блокировкам и «да» скорости!
VenturaVPN — топ-1 VPN в РФ, и я знаю, почему:

🌍 серверы по всему миру
⚡️ суперскорость
🛡️ твоя приватность — наш приоритет
💰 цены, которые радуют

Готов начать? Просто выбери тариф и жми «Подключиться» 😉"""

WELCOME_WITH_SUB = """Твоя подписка на VenturaVPN уже активна!
Вот что у тебя сейчас:

📆 Подписка: {days_left} дней
📱 Устройств: до {max_devices}
⏳ Действует до: {end_date}

Наслаждайся свободным интернетом, быстрой скоростью и надёжной защитой 😉

Если будут вопросы — я рядом ❤️"""

ABOUT_TEXT = """<b>VenturaVPN — интернет без границ.</b>

VenturaVPN — это <i>быстрый и надёжный</i> VPN-сервис для тех, кто ценит свободу в сети. Мы используем <b>качественные серверы</b> и собственные <b>белые IP-адреса</b>, чтобы обеспечить стабильное соединение, высокую скорость и минимальные задержки.

<b>С VenturaVPN вы сможете:</b>
• Обходить блокировки и ограничения.
• Защищать свои данные в общественных Wi-Fi сетях.
• Смотреть любимые сервисы без лишних препятствий.
• Пользоваться интернетом <i>быстро и безопасно</i>.

⚡ <b>Высокая скорость</b>
🔒 <b>Надёжная защита данных</b>
🌍 <b>Серверы в разных странах</b>
📱 <b>Поддержка всех популярных устройств</b>

<i>VenturaVPN — когда нужен интернет таким, каким он должен быть.</i>"""

REFERRAL_TEXT = """🤝 <b>Приводи друзей — получай бонусы!</b>

Хочешь бесплатный VPN ещё дольше? Всё просто:

1️⃣ Отправь друзьям эту ссылку:
🔗 <code>{ref_link}</code>

2️⃣ Друг оплачивает подписку
3️⃣ Вы оба получаете +5 бонусных дней 🎁

📊 <b>Твоя статистика:</b>
👥 Приглашено: {invited}
🎁 Бонусов получено: 0 дней

А если хочешь зарабатывать реальные деньги — пиши в поддержку, расскажем про партнёрку с выплатами 💰"""

ADMIN_MSG = """👑 <b>Админ панель</b>

Управление ботом VenturaVPN:

• Отправка сообщений всем пользователям
• Остановка/запуск бота для всех
• Статистика и аналитика"""

ADMIN_KB = {"inline_keyboard": [
    [{"text": "📢 Отправить сообщение", "callback_data": "admin_broadcast"}],
    [{"text": "⏹ Остановить бота", "callback_data": "admin_stop"}],
    [{"text": "▶️ Запустить бота", "callback_data": "admin_start"}],
    [{"text": "📊 Статистика", "callback_data": "admin_stats"}],
    [{"text": "🔙 Назад", "callback_data": "back_main"}]
]}

def get_main_kb(uid_raw):
    """Get main keyboard based on subscription status."""
    uid = f"tg{uid_raw}"
    status = get_sub_status(uid)
    has_sub = status.get("has_sub", False)

    if has_sub:
        row1 = [{"text": "💎 Подписка", "callback_data": "mysub_menu"}]
    else:
        row1 = [{"text": "🧪 Тест-драйв VPN", "callback_data": "trial"}]

    return {"inline_keyboard": [
        row1,
        [{"text": "🎁Есть код?", "callback_data": "enter_promo"}, {"text": "💰зови друзей", "callback_data": "partner"}],
        [{"text": "Каролина, помоги", "url": "https://t.me/ventura_sup"}, {"text": "О Ventura", "callback_data": "info"}],
        [{"text": "👑 Админ панель", "callback_data": "admin_panel"}]
    ]}

def get_mysub_kb(status):
    """Get subscription menu keyboard."""
    kb = []

    if not status.get("has_sub"):
        kb.append([{"text": "🎁 Пробная (3 дня)", "callback_data": "trial"}])

    buy_text = "✨ Полетели (купить)" if status.get("has_sub") else "💳 Оформить на месяц (200 ₽)"
    kb.append([{"text": buy_text, "callback_data": "buy"}])

    if status.get("has_sub"):
        kb.append([{"text": "🔑 Мой ключ", "callback_data": "get_key"}, {"text": "📱 Устройства", "callback_data": "my_devices"}])
        kb.append([{"text": "🌍 Серверы", "callback_data": "select_subfile"}])

    kb.append([{"text": "🔄 Аккаунты", "callback_data": "sync_menu"}])
    kb.append([{"text": "🔙 Назад", "callback_data": "back_main"}])
    return {"inline_keyboard": kb}

def safe_edit(chat, msg, **kwargs):
    """Safely edit message text."""
    if "photo" in msg:
        api("deleteMessage", chat_id=chat, message_id=msg["message_id"])
        api("sendMessage", chat_id=chat, **kwargs)
    else:
        api("editMessageText", chat_id=chat, message_id=msg["message_id"], **kwargs)

def get_full_bot_stats():
    """Get full bot statistics from panel API."""
    stats = {
        "total_users": 0,
        "active_today": 0,
        "active_week": 0,
        "active_month": 0,
        "total_subscriptions": 0,
        "active_subscriptions": 0,
        "expired_subscriptions": 0,
        "revenue_today": 0.0,
        "revenue_week": 0.0,
        "revenue_month": 0.0,
        "new_users_today": 0,
        "referrals_count": 0,
        "devices_connected": 0,
        "top_servers": [],
        "avg_session_time": 0,
        "uptime_hours": 0
    }

    try:
        req = urllib.request.Request(
            "http://150.241.66.53/api/admin/stats?secret=vpanel_7kQ2xR9mZ",
            headers={"Host": "panel.venturavpn.club"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            panel_stats = json.load(r)

        stats.update(panel_stats)
    except Exception as e:
        print(f"Error getting stats: {e}")

    return stats

def format_uptime(hours):
    """Format uptime hours to readable string."""
    if hours < 24:
        return f"{int(hours)} часов"
    days = int(hours // 24)
    remaining_hours = int(hours % 24)
    if days < 30:
        return f"{days} дней {remaining_hours} часов"
    months = int(days // 30)
    remaining_days = days % 30
    return f"{months} месяцев {remaining_days} дней"

def format_stats_message(stats):
    """Format full statistics message."""
    msg = "📊 <b>МЕГА ПОЛНАЯ статистика бота</b>\n\n"

    msg += "<b>👥 ПОЛЬЗОВАТЕЛИ:</b>\n"
    msg += f"• Всего: <b>{stats['total_users']}</b>\n"
    msg += f"• Новых сегодня: <b>+{stats['new_users_today']}</b>\n"
    msg += f"• Активных сегодня: <b>{stats['active_today']}</b>\n"
    msg += f"• Активных за неделю: <b>{stats['active_week']}</b>\n"
    msg += f"• Активных за месяц: <b>{stats['active_month']}</b>\n\n"

    msg += "<b>💎 ПОДПИСКИ:</b>\n"
    msg += f"• Всего оформлено: <b>{stats['total_subscriptions']}</b>\n"
    msg += f"• Активных сейчас: <b>{stats['active_subscriptions']}</b>\n"
    msg += f"• Истекло: <b>{stats['expired_subscriptions']}</b>\n"
    msg += f"• Устройств подключено: <b>{stats['devices_connected']}</b>\n\n"

    msg += "<b>💰 ДОХОД:</b>\n"
    msg += f"• Сегодня: <b>{stats['revenue_today']:.0f} ₽</b>\n"
    msg += f"• За неделю: <b>{stats['revenue_week']:.0f} ₽</b>\n"
    msg += f"• За месяц: <b>{stats['revenue_month']:.0f} ₽</b>\n\n"

    msg += "<b>🤝 РЕФЕРАЛЫ:</b>\n"
    msg += f"• Всего приглашено: <b>{stats['referrals_count']}</b>\n\n"

    msg += "<b>🌍 ТОП СЕРВЕРЫ:</b>\n"
    if stats['top_servers']:
        for i, server in enumerate(stats['top_servers'][:5], 1):
            name = server.get('name', 'N/A')
            users = server.get('users', 0)
            msg += f"{i}. {name} — <b>{users}</b> пользователей\n"
    else:
        msg += "Данные недоступны\n"

    msg += f"\n<b>⚙️ ТЕХНИЧЕСКОЕ:</b>\n"
    msg += f"• Среднее время сессии: <b>{format_uptime(stats['avg_session_time'])}</b>\n"
    msg += f"• Аптайм бота: <b>{format_uptime(stats['uptime_hours'])}</b>\n"

    return msg

def main():
    if not TOKEN:
        print("ERROR: no BOT_TOKEN"); return

    print("Bot started for @first1523...")
    offset = None

    while True:
        try:
            updates = json.loads(urllib.request.urlopen(f"{API}/getUpdates?offset={offset}&timeout=30", timeout=35).read())
            for upd in updates.get("result", []):
                offset = upd.get("update_id") + 1
                cq = upd.get("callback_query")
                if cq:
                    chat = cq["message"]["chat"]["id"]
                    data = cq["data"]
                    frm = cq.get("from", {})
                    uid_raw = str(frm.get("id"))

                    # ONLY process test user
                    if uid_raw != TEST_USER_ID:
                        continue

                    if data == "back_main":
                        sub_details = get_subscription_details(f"tg{uid_raw}")
                        if sub_details and sub_details.get("has_sub"):
                            welcome_text = WELCOME_WITH_SUB.format(
                                days_left=sub_details["days_left"],
                                max_devices=sub_details["max_devices"],
                                end_date=sub_details["end_date_str"]
                            )
                        else:
                            welcome_text = WELCOME_NO_SUB
                        safe_edit(chat, cq["message"], text=welcome_text, reply_markup=get_main_kb(uid_raw))

                    elif data == "admin_panel":
                        safe_edit(chat, cq["message"], text=ADMIN_MSG, parse_mode="HTML", reply_markup=ADMIN_KB)

                    elif data == "admin_stats":
                        full_stats = get_full_bot_stats()
                        stats_msg = format_stats_message(full_stats)
                        safe_edit(chat, cq["message"], text=stats_msg, parse_mode="HTML", reply_markup=ADMIN_KB)

                    elif data == "info":
                        safe_edit(chat, cq["message"], text=ABOUT_TEXT, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_kb(uid_raw))

                    elif data == "partner":
                        ref_link = f"https://t.me/VenturaVpnRobot?start=ref_{uid_raw}"
                        stats = {"count": 0}  # Placeholder
                        msg_text = REFERRAL_TEXT.format(ref_link=ref_link, invited=stats.get("count", 0))
                        kb = {"inline_keyboard": [
                            [{"text": "Поддержка", "url": "https://t.me/ventura_sup"}],
                            [{"text": "Назад", "callback_data": "back_main"}]
                        ]}
                        safe_edit(chat, cq["message"], text=msg_text, parse_mode="HTML", reply_markup=kb)

                    continue

                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "") or ""
                uid_raw = str(msg["from"]["id"])

                # ONLY process test user
                if uid_raw != TEST_USER_ID:
                    continue

                if text.startswith("/start"):
                    sub_details = get_subscription_details(f"tg{uid_raw}")

                    # Send sticker first
                    STICKER_ID = "CAACAgEAAxkBAAEF3HhqbhZvJWm-aqcFrnAy9S2lK1Xa4gACggoAApH6aEfLT1-_Y898yj0E"
                    api("sendSticker", chat_id=chat_id, sticker=STICKER_ID)

                    if sub_details and sub_details.get("has_sub"):
                        welcome_text = WELCOME_WITH_SUB.format(
                            days_left=sub_details["days_left"],
                            max_devices=sub_details["max_devices"],
                            end_date=sub_details["end_date_str"]
                        )
                    else:
                        welcome_text = WELCOME_NO_SUB

                    api("sendMessage", chat_id=chat_id, text=welcome_text, reply_markup=get_main_kb(uid_raw))

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
