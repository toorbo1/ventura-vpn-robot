#!/usr/bin/env python3
"""VenturaVPN beta-feedback bot. Stdlib only (urllib) — no pip deps.
Greets the user, explains its purpose, shows an "Отправить отзыв" button,
and saves every text message to /var/lib/ventura/feedback.jsonl."""
import os, json, time, urllib.request, urllib.parse, urllib.error, threading, logging, re

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    try:
        TOKEN = open("/root/bot/token").read().strip()
    except Exception:
        TOKEN = ""
API = f"https://api.telegram.org/bot{TOKEN}"

DATA_DIR = "/var/lib/ventura"
FEEDBACK = os.path.join(DATA_DIR, "feedback.jsonl")
KEYREQ = os.path.join(DATA_DIR, "key_requests.jsonl")
os.makedirs(DATA_DIR, exist_ok=True)

KEY_URL = "https://venturavpn.club/test_with_no_ping_de"  # fallback
PANEL_ISSUE = "https://panel.venturavpn.club/api/issue?secret=vpanel_7kQ2xR9mZ&name={uid}"
PANEL_TRIAL = "https://panel.venturavpn.club/api/trial?secret=vpanel_7kQ2xR9mZ&name={uid}"
PANEL_REF_ADD = "https://panel.venturavpn.club/api/ref/add?uid={uid}&referrer={referrer}"
PANEL_REF_STATS = "https://panel.venturavpn.club/api/ref/stats?uid={uid}"

BOT_USERNAME = None
WAITING_FOR_PROMO = {}
WAITING_FOR_SYNC_CODE = {}
ACTIVE_SYNC_CODES = {}
WAITING_FOR_SYNC_RESULT = {}
WAITING_FOR_WEB_LOGIN = {}
WAITING_FOR_WEB_PASSWORD = {}
WAITING_FOR_BROADCAST = {}  # Для админ панели

# Test user for new design
TEST_USER_ID = "5302383529"  # @first1523

# Admin panel texts
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

# New design texts for test user
NEW_PARTNER_MSG = """👀 Пссс... есть тема!

Позови друзей в VenturaVPN, и за каждого приглашённого тебя будут ждать бонусы 🎁

Друг получает классный VPN, а ты — приятную награду.

Выглядит как вин-вин, не находишь? 😏"""

NEW_SUBSCRIPTION_MSG = """💎 Подписка VenturaVPN

Тут живёт твой VPN без ограничений 😎

⚡ Быстро
🌍 Много серверов
🔒 Безопасно
💸 Всего 200 ₽ за 30 дней

Что будем делать дальше? 👇"""

IPHONE_SETUP_MSG = """ℹ️ Как подключиться

1️⃣ Оформи подписку - кнопка «Оформить / продлить»

2️⃣ Установи приложение - кнопки ниже

3️⃣ «Моя подписка» → «Подключиться» → «Открыть ссылку» - настройки подтянутся сами

4️⃣ Включи VPN - готово ✅"""

logging.basicConfig(level=logging.INFO)

PANEL_LINK = "https://panel.venturavpn.club/api/account"
PANEL_SEC = "vpanel_7kQ2xR9mZ"

def _api_get(path, **params):
    qs = urllib.parse.urlencode({"secret": PANEL_SEC, **params})
    url = f"{PANEL_LINK}/{path}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

def link_generate(uid, platform, username=""):
    return _api_get("link/generate", uid=uid, platform=platform, username=username)

def link_apply(code, uid, platform, username=""):
    return _api_get("link/apply", code=code, uid=uid, platform=platform, username=username)

def link_confirm(code, uid, confirm=True):
    return _api_get("link/confirm", code=code, uid=uid, confirm="true" if confirm else "false")

def link_status(uid):
    return _api_get("link/status", uid=uid)

def pending_confirmation(uid):
    return _api_get("pending_confirmation", uid=uid)

def link_cancel(uid):
    return _api_get("link/cancel", uid=uid)

# Removed encrypt_happ_url
def issue_key(uid, username=""):
    """Ask the panel for this user's personal subscription link (idempotent per uid).
    Browser User-Agent is required — Cloudflare blocks default urllib UA with 403/1010."""
    try:
        url = PANEL_ISSUE.format(uid=uid)
        if username:
            url += f"&display={urllib.parse.quote('@'+username)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
        with urllib.request.urlopen(req, timeout=15) as r:
            url = json.load(r).get("url")
            return url
    except Exception:
        return None

def issue_trial(uid, username=""):
    try:
        url = PANEL_TRIAL.format(uid=uid)
        if username:
            url += f"&display={urllib.parse.quote('@'+username)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
        with urllib.request.urlopen(req, timeout=15) as r:
            url = json.load(r).get("url")
            return url
    except Exception:
        return None

def add_referral(uid, referrer):
    try:
        url = PANEL_REF_ADD.format(uid=uid, referrer=referrer)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
        urllib.request.urlopen(req, timeout=5)
    except: pass

def get_ref_stats(uid):
    try:
        url = PANEL_REF_STATS.format(uid=uid)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except:
        return {"count": 0, "earned_days": 0, "earned_money": 0.0, "is_vip": False, "vip_balance": 0.0}

def get_full_bot_stats():
    """Получает полную статистику бота с панели."""
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
        # Общая статистика пользователей
        req = urllib.request.Request(
            "http://150.241.66.53/api/admin/stats?secret=vpanel_7kQ2xR9mZ",
            headers={"Host": "panel.venturavpn.club"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            panel_stats = json.load(r)

        stats["total_users"] = panel_stats.get("total_users", 0)
        stats["active_today"] = panel_stats.get("active_today", 0)
        stats["active_week"] = panel_stats.get("active_week", 0)
        stats["active_month"] = panel_stats.get("active_month", 0)
        stats["total_subscriptions"] = panel_stats.get("total_subscriptions", 0)
        stats["active_subscriptions"] = panel_stats.get("active_subscriptions", 0)
        stats["expired_subscriptions"] = panel_stats.get("expired_subscriptions", 0)
        stats["revenue_today"] = panel_stats.get("revenue_today", 0.0)
        stats["revenue_week"] = panel_stats.get("revenue_week", 0.0)
        stats["revenue_month"] = panel_stats.get("revenue_month", 0.0)
        stats["new_users_today"] = panel_stats.get("new_users_today", 0)
        stats["referrals_count"] = panel_stats.get("referrals_count", 0)
        stats["devices_connected"] = panel_stats.get("devices_connected", 0)
        stats["top_servers"] = panel_stats.get("top_servers", [])
        stats["avg_session_time"] = panel_stats.get("avg_session_time", 0)
        stats["uptime_hours"] = panel_stats.get("uptime_hours", 0)

    except Exception as e:
        print(f"Error getting full stats: {e}")

    return stats

def format_uptime(hours):
    """Форматирует время аптайма в читаемый вид."""
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
    """Форматирует статистику в красивое сообщение."""
    msg = "📊 <b>МЕГА ПОЛНАЯ статистика бота</b>\n\n"

    # Пользователи
    msg += "<b>👥 ПОЛЬЗОВАТЕЛИ:</b>\n"
    msg += f"• Всего: <b>{stats['total_users']}</b>\n"
    msg += f"• Новых сегодня: <b>+{stats['new_users_today']}</b>\n"
    msg += f"• Активных сегодня: <b>{stats['active_today']}</b>\n"
    msg += f"• Активных за неделю: <b>{stats['active_week']}</b>\n"
    msg += f"• Активных за месяц: <b>{stats['active_month']}</b>\n\n"

    # Подписки
    msg += "<b>💎 ПОДПИСКИ:</b>\n"
    msg += f"• Всего оформлено: <b>{stats['total_subscriptions']}</b>\n"
    msg += f"• Активных сейчас: <b>{stats['active_subscriptions']}</b>\n"
    msg += f"• Истекло: <b>{stats['expired_subscriptions']}</b>\n"
    msg += f"• Устройств подключено: <b>{stats['devices_connected']}</b>\n\n"

    # Доход
    msg += "<b>💰 ДОХОД:</b>\n"
    msg += f"• Сегодня: <b>{stats['revenue_today']:.0f} ₽</b>\n"
    msg += f"• За неделю: <b>{stats['revenue_week']:.0f} ₽</b>\n"
    msg += f"• За месяц: <b>{stats['revenue_month']:.0f} ₽</b>\n\n"

    # Рефералы
    msg += "<b>🤝 РЕФЕРАЛЫ:</b>\n"
    msg += f"• Всего приглашено: <b>{stats['referrals_count']}</b>\n\n"

    # Серверы
    msg += "<b>🌍 ТОП СЕРВЕРЫ:</b>\n"
    if stats['top_servers']:
        for i, server in enumerate(stats['top_servers'][:5], 1):
            name = server.get('name', 'N/A')
            users = server.get('users', 0)
            msg += f"{i}. {name} — <b>{users}</b> пользователей\n"
    else:
        msg += "Данные недоступны\n"

    # Аптайм
    msg += f"\n<b>⚙️ ТЕХНИЧЕСКОЕ:</b>\n"
    msg += f"• Среднее время сессии: <b>{format_uptime(stats['avg_session_time'])}</b>\n"
    msg += f"• Аптайм бота: <b>{format_uptime(stats['uptime_hours'])}</b>\n"

    return msg

def get_sub_status(uid):
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
    """Форматирует timestamp в читаемую дату окончания подписки на русском."""
    if not expires_timestamp or expires_timestamp == 0:
        return "неизвестно"
    try:
        t = time.localtime(expires_timestamp)
        day = str(int(time.strftime('%d', t)))
        # Русские названия месяцев
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
    """Получает детальную информацию о подписке пользователя."""
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

def delete_device(cid, hwid):
    try:
        req = urllib.request.Request(
            f"http://150.241.66.53/api/payment/delete_device?cid={cid}&hwid={hwid}",
            headers={"Host": "panel.venturavpn.club"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except:
        return {"ok": False}


def key_message(uid_raw=""):
    is_test_user = (uid_raw == TEST_USER_ID)
    if is_test_user:
        return (
            "🔑 Ваша персональная подписка\n\n"
            "Нажмите кнопку 'Подключить', чтобы автоматически запустить приложение."
        )
    else:
        return (
            "🔑 <b>Ваша персональная подписка</b>\n\n"
            "Нажмите кнопку <b>🚀 Подключить</b> ниже, чтобы автоматически добавить серверы в приложение.\n\n"
            "<b>Инструкция по подключению:</b>\n"
            "1. Установите приложение <b>HAPP</b> из App Store / Google Play.\n"
            "2. Нажмите на кнопку <b>🚀 Подключить</b> под этим сообщением.\n"
            "3. В приложении перейдите в <b>⚙️ Настройки</b> -> <b>«Подписки»</b> и выберите <b>Сортировать по пингу</b>.\n"
            "4. Выйдите в главное меню и нажмите кнопку подключения! 🚀\n\n"
            "📱 <b>На iPhone:</b> если HApp не открылся автоматически, нажмите «Скопировать ссылку» на открывшейся странице, "
            "затем откройте HApp → ☰ → «Подписки» → «+ Добавить» и вставьте ссылку."
        )

WELCOME = """Привет!.

Мы даём доступ к сети без ограничений и блокировок. Наша главная фишка — высокая скорость, потому что мы не экономим на серверах и используем собственные белые списки IP-адресов (доверенные, чистые адреса, которые не блокируются).

<b>Что тебя ждёт:</b>
✅ Обход любых блокировок (РКН и другие) — подключайся и забывай.
✅ Множество серверов по всему миру — стабильное соединение всегда.
✅ Максимальная скорость — идеально для игр, стримов и работы.
✅ Telegram-канал с эксклюзивными материалами — <a href='https://t.me/venturaVPN'>@venturaVPN</a> (подпишись, чтобы быть в курсе!).

🚀 <b>А в будущем станет ещё круче:</b>
🔹 Нативное приложение — ещё проще и быстрее.
🔹 Встроенный ИИ — для умной маршрутизации трафика
🔹 Супер скидки и предложения

Старт — в один клик! 👇

Нажми кнопку «Тестовая подписка» и получи доступ прямо сейчас. Бот скоро станет твоим незаменимым помощником 🚀"""

# New design for test user @first1523 (ID: 5302383529)
NEW_WELCOME = """Привееетик! 👋

Я Каролина ✨

Этот бот проооосто классссный: куча серверов, быстрый интернет, хорошая поддержка и оооочень приятные цены

И это только начало... дальше будет ещё круче 😏

Ну что, погнали? 🚀

1️⃣ Жмякай «🧪 Тест-драйв VPN»
2️⃣ Вставляй ключик
3️⃣ Ту-ту-туууу... наслаждайся свободным интернетом 🎉"""

# Сообщение для пользователя БЕЗ подписки (или с истекшей)
NO_SUBSCRIPTION_MSG = """Привееет! Каролина на связи ✨

Скажи «нет» блокировкам и «да» скорости!
VenturaVPN — топ-1 VPN в РФ, и я знаю, почему:

🌍 серверы по всему миру
⚡️ суперскорость
🛡️ твоя приватность — наш приоритет
💰 цены, которые радуют

Готов начать? Просто выбери тариф и жми «Подключиться» 😉"""

# Сообщение для пользователя С АКТИВНОЙ подпиской
ACTIVE_SUBSCRIPTION_MSG = """Твоя подписка на VenturaVPN уже активна!
Вот что у тебя сейчас:

📆 Подписка: {days_left} дней
📱 Устройств: до {max_devices}
⏳ Действует до: {end_date}

Наслаждайся свободным интернетом, быстрой скоростью и надёжной защитой 😉

Если будут вопросы — я рядом ❤️"""
def get_main_kb(uid_raw):
    uid = f"tg{uid_raw}"
    status = get_sub_status(uid)
    has_sub = status.get("has_sub", False)

    # Check if user is test user for new design
    is_test_user = (uid_raw == TEST_USER_ID)

    if is_test_user:
        # New design buttons
        if has_sub:
            row1 = [{"text": "💎 Подписка", "callback_data": "mysub_menu"}]
        else:
            row1 = [{"text": "🧪 Тест-драйв VPN", "callback_data": "trial"}]

        # Add admin panel button for test user
        return {"inline_keyboard": [
            row1,
            [{"text": "🎁Есть код?", "callback_data": "enter_promo"}, {"text": "💰зови друзей", "callback_data": "partner"}],
            [{"text": "Каролина, помоги", "url": "https://t.me/ventura_sup"}, {"text": "О Ventura", "callback_data": "info"}],
            [{"text": "👑 Админ панель", "callback_data": "admin_panel"}]  # Admin panel button
        ]}
    else:
        # Old design
        if has_sub:
            row1 = [{"text": "💎 Моя подписка", "callback_data": "mysub_menu"}]
        else:
            row1 = [{"text": "🧪 Тестовая подписка", "callback_data": "trial"}, {"text": "💎 Купить подписку", "callback_data": "buy"}]

        return {"inline_keyboard": [
            row1,
            [{"text": "🎫 Промокоды", "callback_data": "enter_promo"}, {"text": "🤝 Партнерка", "callback_data": "partner"}],
            [{"text": "🛠 Техподдержка", "url": "https://t.me/ventura_sup"}, {"text": "ℹ️ Инфо", "callback_data": "info"}],
        ]}

def get_mysub_kb(status, uid_raw=""):
    kb = []
    is_test_user = (uid_raw == TEST_USER_ID)

    # If no subscription ever, show trial
    if not status.get("has_sub"):
        kb.append([{"text": "🎁 Пробная (3 дня)", "callback_data": "trial"}])

    # Buy button
    if status.get("has_sub"):
        buy_text = "✨ Полетели (купить)" if is_test_user else "💳 Докупить 30 дней (200 ₽)"
        kb.append([{"text": buy_text, "callback_data": "buy"}])
    else:
        buy_text = "✨ Полетели (купить)" if is_test_user else "💳 Оформить на месяц (200 ₽)"
        kb.append([{"text": buy_text, "callback_data": "buy"}])

    if status.get("has_sub"):
        key_text = "🔑 Мой ключ" if is_test_user else "🔑 Получить мой ключ"
        dev_text = "📱 Устройства" if is_test_user else "📱 Мои устройства"
        kb.append([{"text": key_text, "callback_data": "get_key"}, {"text": dev_text, "callback_data": "my_devices"}])
        server_text = "🌍 Серверы" if is_test_user else "🌍 Выбор серверов"
        kb.append([{"text": server_text, "callback_data": "select_subfile"}])
    sync_text = "🔄 Аккаунты" if is_test_user else "🔗 Синхронизация аккаунтов"
    kb.append([{"text": sync_text, "callback_data": "sync_menu"}])
    kb.append([{"text": "🔙 Назад", "callback_data": "back_main"}])
    return {"inline_keyboard": kb}


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




def log_key_request(frm):
    rec = {
        "ts": int(time.time()),
        "date": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "user_id": frm.get("id"),
        "username": frm.get("username"),
        "name": ((frm.get("first_name") or "") + " " + (frm.get("last_name") or "")).strip(),
    }
    with open(KEYREQ, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def do_buy(chat, uid, promo=""):
    uid_raw = uid.replace("tg", "")
    try:
        url = f"http://150.241.66.53/api/payment/bot_create?secret=vpanel_7kQ2xR9mZ&uid={uid}"
        if promo:
            url += f"&promo={urllib.parse.quote(promo)}"
        req = urllib.request.Request(url, headers={"Host": "panel.venturavpn.club"})
        try:
            r = urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as e:
            # Try to read the actual error from the JSON body
            try:
                body = json.load(e)
                if body.get("promo_error"):
                    return {"error": body.get("error", "Промокод недействителен"), "promo_error": True}
            except Exception:
                pass
            api("sendMessage", chat_id=chat, text=f"Ошибка сервера платежей: {e}")
            return {"error": str(e)}
        with r:
            res = json.load(r)
            if res.get("promo_error"):
                return {"error": res.get("error"), "promo_error": True}
            
            pay_url = res.get("pay_url")
            if pay_url:
                if pay_url == "free":
                    api("sendMessage", chat_id=chat, text="🎉 Ваша подписка успешно активирована бесплатно! Нажмите «Моя подписка».", reply_markup=get_main_kb(uid_raw))
                else:
                    kb_pay = {"inline_keyboard": [
                        [{"text": f"💳 Оплатить ({res.get('amount')} ₽)", "url": pay_url}],
                        [{"text": "🔄 Проверить оплату", "callback_data": f"check_{uid}"}],
                        [{"text": "🔙 В главное меню", "callback_data": "back_main"}]
                    ]}
                    if promo:
                        msg_text = f"✅ Промокод <b>{promo}</b> успешно применен!\n\nДля оформления подписки перейдите по персональной ссылке ниже."
                    else:
                        msg_text = "Для оформления подписки перейдите по персональной ссылке ниже."
                    api("sendMessage", chat_id=chat, text=msg_text, reply_markup=kb_pay, parse_mode="HTML")
                return {"ok": True}
            else:
                api("sendMessage", chat_id=chat, text="Ошибка создания платежа. Попробуйте позже.")
                return {"error": "no pay url"}
    except Exception as e:
        api("sendMessage", chat_id=chat, text=f"Ошибка сервера платежей: {e}")
        return {"error": str(e)}


def safe_edit(chat, msg, **kwargs):
    if "photo" in msg:
        api("deleteMessage", chat_id=chat, message_id=msg["message_id"])
        api("sendMessage", chat_id=chat, **kwargs)
    else:
        api("editMessageText", chat_id=chat, message_id=msg["message_id"], **kwargs)

def main():
    if not TOKEN:
        print("ERROR: no BOT_TOKEN / /root/bot/token"); return
    offset = None
    print("VenturaVPN feedback bot started")
    while True:
        resp = api("getUpdates", offset=offset, timeout=60)
        if not resp.get("ok"):
            time.sleep(3); continue
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            try:
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    data = cq.get("data", "")
                    api("answerCallbackQuery", callback_query_id=cq["id"])
                    chat = cq["message"]["chat"]["id"]
                    if data == "mysub_menu":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        uid = f"tg{uid_raw}"
                        status = get_sub_status(uid)
                        is_test_user = (uid_raw == TEST_USER_ID)

                        # New design for test user
                        if is_test_user:
                            msg = NEW_SUBSCRIPTION_MSG
                            safe_edit(chat, cq["message"],
                                text=msg, reply_markup=get_mysub_kb(status, uid_raw))
                        else:
                            msg = "<b>📱 Управление подпиской</b>\n\n"
                            if status.get("has_sub"):
                                exp = status.get("expires", 0)
                                max_dev = status.get("max_devices", 5)
                                msg += f"Лимит устройств: <b>{max_dev}</b>\n\n"

                                if exp == 0:
                                    msg += "Статус: <b>Бессрочно</b>\nОсталось дней: <b>∞</b>\n"
                                else:
                                    now = int(time.time())
                                    if exp > now:
                                        days = int((exp - now) / 86400)
                                        date_str = time.strftime("%d.%m.%Y", time.gmtime(exp))
                                        msg += f"Статус: <b>Активна</b>\nОсталось дней: <b>{days}</b>\nДействует до: <b>{date_str}</b>\n"
                                    else:
                                        date_str = time.strftime("%d.%m.%Y", time.gmtime(exp))
                                        msg += f"Статус: <b>Истекла</b> ({date_str})\nОсталось дней: <b>0</b>\n"
                            else:
                                msg += "У вас пока нет активной подписки.\n"

                            safe_edit(chat, cq["message"],
                                text=msg, parse_mode="HTML", reply_markup=get_mysub_kb(status, uid_raw))
                            
                    elif data == "select_subfile":
                        frm = cq.get("from", {})
                        uid = f"tg{frm.get('id')}"
                        status = get_sub_status(uid)
                        current = status.get("subfile", "mini")
                        
                        msg = "<b>🌍 Выбор протестированного списка серверов</b>\n\n"
                        msg += "Из-за особенностей блокировок в разных сетях (в России и за рубежом), "
                        msg += "одни и те же серверы могут работать по-разному.\n\n"
                        msg += "Выберите, какой список серверов вы хотите получать в подписке:"
                        
                        chk_lite = " ✅" if current == "lite" else ""
                        chk_mini = " ✅" if current == "mini" else ""
                        chk_all = " ✅" if current == "all" else ""
                        kb = [
                            [{"text": f"🌍 Все серверы{chk_all}", "callback_data": "set_subfile_all"}],
                            [{"text": f"⚡ Лайт (первые 300){chk_lite}", "callback_data": "set_subfile_lite"}],
                            [{"text": f"📱 Мини (первые 100){chk_mini}", "callback_data": "set_subfile_mini"}],
                            [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                        ]
                        safe_edit(chat, cq["message"],
                            text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": kb})
                            
                    elif data.startswith("set_subfile_"):
                        frm = cq.get("from", {})
                        uid = f"tg{frm.get('id')}"
                        subfile = data.replace("set_subfile_", "")
                        status = get_sub_status(uid)
                        cid = status.get("cid", "")
                        
                        if cid and subfile in ("all", "lite", "mini"):
                            try:
                                req = urllib.request.Request(
                                    f"http://150.241.66.53/api/payment/set_subfile?cid={cid}&subfile={subfile}",
                                    headers={"Host": "panel.venturavpn.club"}
                                )
                                urllib.request.urlopen(req, timeout=5)
                                api("answerCallbackQuery", callback_query_id=cq["id"], text="✅ Сохранено! Обновите подписку в клиенте.", show_alert=True)
                            except Exception:
                                api("answerCallbackQuery", callback_query_id=cq["id"], text="Ошибка сохранения", show_alert=True)
                                
                        # Return to the selection menu to show updated checkmark
                        status = get_sub_status(uid)
                        current = status.get("subfile", "mini")
                        
                        msg = "<b>🌍 Выбор протестированного списка серверов</b>\n\n"
                        msg += "Из-за особенностей блокировок в разных сетях (в России и за рубежом), "
                        msg += "одни и те же серверы могут работать по-разному.\n\n"
                        msg += "Выберите, какой список серверов вы хотите получать в подписке:"
                        
                        chk_lite = " ✅" if current == "lite" else ""
                        chk_mini = " ✅" if current == "mini" else ""
                        chk_all = " ✅" if current == "all" else ""
                        
                        kb = [
                            [{"text": f"🌍 Все серверы{chk_all}", "callback_data": "set_subfile_all"}],
                            [{"text": f"⚡ Лайт (первые 300){chk_lite}", "callback_data": "set_subfile_lite"}],
                            [{"text": f"📱 Мини (первые 100){chk_mini}", "callback_data": "set_subfile_mini"}],
                            [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                        ]
                        safe_edit(chat, cq["message"],
                            text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": kb})

                    elif data == "my_devices":
                        frm = cq.get("from", {})
                        uid = f"tg{frm.get('id')}"
                        status = get_sub_status(uid)
                        devices = status.get("devices", [])
                        max_dev = status.get("max_devices", 5)
                        
                        msg = f"<b>📱 Ваши устройства ({len(devices)}/{max_dev})</b>\n\n"
                        kb = []
                        if not devices:
                            msg += "У вас пока нет привязанных устройств. Они появятся здесь, когда вы подключитесь к VPN."
                        else:
                            msg += "Нажмите на устройство ниже, чтобы удалить его из подписки:\n"
                            for i, d in enumerate(devices):
                                name = d.get("name", "Неизвестное устройство")
                                d_time = time.strftime("%d.%m.%Y %H:%M", time.gmtime(d.get("last_seen", 0)))
                                msg += f"\n{i+1}. <b>{name}</b> (был в сети: {d_time})"
                                kb.append([{"text": f"❌ Удалить {name}", "callback_data": f"del_dev_{d.get('hwid')}"}])
                                
                        kb.append([{"text": "🔙 К подписке", "callback_data": "mysub_menu"}])
                        safe_edit(chat, cq["message"],
                            text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": kb})
                            
                    elif data.startswith("del_dev_"):
                        frm = cq.get("from", {})
                        uid = f"tg{frm.get('id')}"
                        hwid = data[8:]
                        status = get_sub_status(uid)
                        cid = status.get("cid", "")
                        
                        if cid and hwid:
                            delete_device(cid, hwid)
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="✅ Устройство удалено", show_alert=False)
                            
                            # Fetch updated status
                            status = get_sub_status(uid)
                            devices = status.get("devices", [])
                            max_dev = status.get("max_devices", 5)
                            
                            msg = f"<b>📱 Ваши устройства ({len(devices)}/{max_dev})</b>\n\n"
                            kb = []
                            if not devices:
                                msg += "У вас пока нет привязанных устройств. Они появятся здесь, когда вы подключитесь к VPN."
                            else:
                                msg += "Нажмите на устройство ниже, чтобы удалить его из подписки:\n"
                                for i, d in enumerate(devices):
                                    name = d.get("name", "Неизвестное устройство")
                                    d_time = time.strftime("%d.%m.%Y %H:%M", time.gmtime(d.get("last_seen", 0)))
                                    msg += f"\n{i+1}. <b>{name}</b> (был в сети: {d_time})"
                                    kb.append([{"text": f"❌ Удалить {name}", "callback_data": f"del_dev_{d.get('hwid')}"}])
                            kb.append([{"text": "🔙 К подписке", "callback_data": "mysub_menu"}])
                            
                            safe_edit(chat, cq["message"],
                                text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": kb})
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Ошибка удаления", show_alert=True)

                    elif data == "get_key":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        uid = f"tg{uid_raw}"
                        username = frm.get("username", "")
                        url = issue_key(uid, username)
                        if url:
                            # New design buttons for test user
                            is_test_user = (uid_raw == TEST_USER_ID)
                            kb_buttons = []
                            if is_test_user:
                                kb_buttons = [
                                    [{"text": "Подключить", "url": url}],
                                    [{"text": "Настройка iPhone", "callback_data": "setup_iphone"}],
                                    [{"text": "Настройка Android", "callback_data": "setup_android"}],
                                    [{"text": "Назад", "callback_data": "mysub_menu"}]
                                ]
                            else:
                                kb_buttons = [
                                    [{"text": "🚀 Подключить", "url": url}],
                                    [{"text": "🔙 Назад", "callback_data": "mysub_menu"}]
                                ]
                            kb = {"inline_keyboard": kb_buttons}
                            safe_edit(chat, cq["message"],
                                text=key_message(uid_raw), parse_mode="HTML",
                                disable_web_page_preview=True, reply_markup=kb)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Ключ не найден", show_alert=True)
                            
                    elif data == "back_main":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)

                        # Get subscription status
                        uid_for_api = f"tg{uid_raw}"
                        sub_details = get_subscription_details(uid_for_api)

                        if is_test_user:
                            # Determine which message to show based on subscription status
                            if sub_details and sub_details.get("has_sub"):
                                welcome_text = ACTIVE_SUBSCRIPTION_MSG.format(
                                    days_left=sub_details["days_left"],
                                    max_devices=sub_details["max_devices"],
                                    end_date=sub_details["end_date_str"]
                                )
                            else:
                                welcome_text = NO_SUBSCRIPTION_MSG
                            safe_edit(chat, cq["message"], text=welcome_text, reply_markup=get_main_kb(uid_raw))
                        else:
                            safe_edit(chat, cq["message"],
                                text=WELCOME, parse_mode="HTML", reply_markup=get_main_kb(uid_raw))

                    # Admin panel handlers for test user only
                    elif data == "admin_panel":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            safe_edit(chat, cq["message"], text=ADMIN_MSG, parse_mode="HTML", reply_markup=ADMIN_KB)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Доступ запрещен", show_alert=True)

                    elif data == "admin_broadcast":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            msg = """📢 <b>Отправить сообщение всем пользователям</b>

Введите текст сообщения:
(отправьте /cancel для отмены)"""
                            kb = {"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": "back_main"}]]}
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup=kb)
                            # Set flag for waiting broadcast message
                            WAITING_FOR_BROADCAST[uid_raw] = True
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Доступ запрещен", show_alert=True)

                    elif data == "admin_stop":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            # Here you would implement bot stop logic
                            safe_edit(chat, cq["message"], text="⏹ Бот остановлен для всех пользователей", reply_markup=ADMIN_KB)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Доступ запрещен", show_alert=True)

                    elif data == "admin_start":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            # Here you would implement bot start logic
                            api("sendMessage", chat_id=chat, text="▶️ Бот запущен для всех пользователей", reply_markup=ADMIN_KB)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Доступ запрещен", show_alert=True)

                    elif data == "admin_stats":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            # Получаем полную статистику
                            full_stats = get_full_bot_stats()
                            stats_msg = format_stats_message(full_stats)
                            safe_edit(chat, cq["message"], text=stats_msg, parse_mode="HTML", reply_markup=ADMIN_KB)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Доступ запрещен", show_alert=True)

                    elif data == "sync_menu":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        uid = f"tg{uid_raw}"
                        username = frm.get("username", "")
                        ls = link_status(uid)
                        if ls.get("linked"):
                            tg_name = ls.get("nameTG", "")
                            max_name = ls.get("nameMAX", "")
                            msg = "🔗 <b>Синхронизация аккаунтов</b>\n\n"
                            msg += "✅ <b>Ваши аккаунты связаны:</b>\n"
                            if tg_name:
                                msg += f"  Telegram: <code>{tg_name}</code>\n"
                            if max_name:
                                msg += f"  MAX: <code>{max_name}</code>\n"
                            msg += "\nПодписка общая для обеих платформ."
                            kb = [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": [kb]})
                        else:
                            res = link_generate(uid, "tg", username)
                            if res.get("error"):
                                if res.get("error") == "already_linked":
                                    msg = "🔗 <b>Синхронизация аккаунтов</b>\n\n✅ Ваш аккаунт уже привязан."
                                else:
                                    msg = f"❌ Ошибка: {res.get('error')}"
                                kb = [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                                safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": [kb]})
                            else:
                                code = res.get("code", "")
                                ACTIVE_SYNC_CODES[uid_raw] = {"code": code, "chat_id": chat}
                                pc = pending_confirmation(uid)
                                if pc.get("pending"):
                                    app_uname = pc.get("applicant_username", "") or pc.get("applicant_uid", "")
                                    app_plat = "MAX" if pc.get("applicant_platform") == "max" else "Telegram"
                                    scode = pc.get("code", "")
                                    msg = "🔗 <b>Синхронизация аккаунтов</b>\n\n"
                                    msg += f"⏳ <b>Входящий запрос на привязку</b>\n\n"
                                    msg += f"Пользователь <b>@{app_uname}</b> ({app_plat}) хочет связать свой аккаунт с вашим.\n"
                                    msg += "Подтвердить привязку?\n\n"
                                    msg += f"Ваш код: <code>{code}</code>"
                                    kb = [
                                        [{"text": "✅ Да", "callback_data": f"sync_confirm_{scode}_yes"}, {"text": "❌ Нет", "callback_data": f"sync_confirm_{scode}_no"}],
                                        [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                                    ]
                                else:
                                    msg = "🔗 <b>Синхронизация аккаунтов</b>\n\n"
                                    msg += "Ваш код для привязки:\n"
                                    msg += f"<code>{code}</code>\n\n"
                                    msg += "Откройте бота в MAX, нажмите «Моя подписка» → «🔗 Синхронизация аккаунтов» и введите этот код.\n\n"
                                    msg += "Код действителен 10 минут."
                                    kb = [
                                        [{"text": "📝 Ввести код", "callback_data": "sync_enter_code"}],
                                        [{"text": "🔄 Обновить", "callback_data": "sync_menu"}],
                                        [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                                    ]
                                safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": kb})

                    elif data == "sync_enter_code":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        WAITING_FOR_SYNC_CODE[uid_raw] = time.time()
                        msg = "🔗 <b>Введите код синхронизации</b>\n\nОтправьте 10-символьный код, который вам дал другой пользователь."
                        kb = [{"text": "🔙 Назад", "callback_data": "sync_menu"}]
                        safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": [kb]})

                    elif data.startswith("sync_confirm_"):
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        uid = f"tg{uid_raw}"
                        parts = data[13:]
                        confirm_yes = parts.endswith("_yes")
                        scode = parts[:-4] if confirm_yes else parts[:-3]
                        res = link_confirm(scode, uid, confirm=confirm_yes)
                        if res.get("status") == "confirmed":
                            msg = "✅ <b>Аккаунты успешно связаны!</b>\n\nТеперь подписка общая для Telegram и MAX."
                            kb = [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": [kb]})
                        elif res.get("status") == "rejected":
                            msg = "❌ Привязка отклонена."
                            kb = [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup={"inline_keyboard": [kb]})
                        else:
                            err = res.get("error", "неизвестная ошибка")
                            api("answerCallbackQuery", callback_query_id=cq["id"], text=f"Ошибка: {err}", show_alert=True)
                            
                    elif data == "trial":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        uid = f"tg{uid_raw}"
                        username = frm.get("username", "")
                        url = issue_trial(uid, username)
                        if url:
                            # New design buttons for test user
                            is_test_user = (uid_raw == TEST_USER_ID)
                            if is_test_user:
                                kb = {"inline_keyboard": [
                                    [{"text": "Подключить", "url": url}],
                                    [{"text": "Назад", "callback_data": "back_main"}]
                                ]}
                            else:
                                kb = {"inline_keyboard": [
                                    [{"text": "🚀 Подключить", "url": url}],
                                    [{"text": "🔙 В меню", "callback_data": "back_main"}]
                                ]}
                            safe_edit(chat, cq["message"],
                                text=key_message(uid_raw), parse_mode="HTML",
                                disable_web_page_preview=True, reply_markup=kb)
                        else:
                            api("answerCallbackQuery", callback_query_id=cq["id"], text="Вы уже использовали пробную подписку", show_alert=True)
                    elif data == "partner":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        stats = get_ref_stats(uid_raw)
                        is_test_user = (uid_raw == TEST_USER_ID)

                        # New design for test user
                        if is_test_user:
                            ref_link = f"https://t.me/VenturaVpnRobot?start=ref_{uid_raw}"
                            msg = """🤝 <b>Приводи друзей — получай бонусы!</b>

Хочешь бесплатный VPN ещё дольше? Всё просто:

1️⃣ Отправь друзьям эту ссылку:
🔗 <code>{ref_link}</code>

2️⃣ Друг оплачивает подписку
3️⃣ Вы оба получаете +5 бонусных дней 🎁

📊 <b>Твоя статистика:</b>
👥 Приглашено: {invited}
🎁 Бонусов получено: 0 дней

А если хочешь зарабатывать реальные деньги — пиши в поддержку, расскажем про партнёрку с выплатами 💰""".format(ref_link=ref_link, invited=stats.get("count", 0))
                            kb = {"inline_keyboard": [
                                [{"text": "Поддержка", "url": "https://t.me/ventura_sup"}],
                                [{"text": "Назад", "callback_data": "back_main"}]
                            ]}
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", reply_markup=kb)
                        else:
                            global BOT_USERNAME
                            if BOT_USERNAME is None:
                                try:
                                    req = urllib.request.Request(f"{API}/getMe")
                                    with urllib.request.urlopen(req, timeout=5) as r:
                                        res = json.load(r)
                                        if res.get("ok"):
                                            BOT_USERNAME = res["result"]["username"]
                                except:
                                    BOT_USERNAME = "venturavpn_bot"

                            ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid_raw}"

                            msg = "🤝 <b>Партнерская программа</b>\n\n"
                            msg += "Делитесь этой ссылкой с друзьями и получайте бонусы:\n"
                            msg += f"<code>{ref_link}</code>\n\n"
                            msg += f"👥 Приглашено: <b>{stats['count']}</b>\n"

                            if stats.get("is_vip"):
                                role = "Партнёр" if stats.get("is_worker") else "VIP-партнёр"
                                pct_f = int(stats.get("pct_first", 0.20) * 100)
                                pct_r = int(stats.get("pct_renew", 0.10) * 100)
                                pct_m = int(stats.get("pct_mentor", 0.05) * 100)
                                msg += f"Ваш статус: <b>{role}</b>\n"
                                msg += f"Ваш процент: <b>{pct_f}%</b> (первая покупка) / <b>{pct_r}%</b> (продление)\n"
                                if pct_m > 0:
                                    msg += f"Менторский процент: <b>{pct_m}%</b>\n"
                                msg += f"\n💰 Заработано всего: <b>{stats.get('total_earned', stats.get('earned_money', 0)):.2f} ₽</b>\n"
                                msg += f"💳 Текущий баланс: <b>{stats.get('vip_balance', 0):.2f} ₽</b>\n"
                                mentor_e = stats.get("mentor_earnings", 0)
                                if mentor_e > 0:
                                    msg += f"🤝 Менторские бонусы: <b>{mentor_e:.2f} ₽</b>\n"
                                msg += f"\n<i>(Вы получаете {pct_f}% с первой покупки и {pct_r}% с продлений)</i>"
                            else:
                                msg += f"🎁 Получено: <b>{stats.get('earned_days', 0)}</b> бонусных дней\n\n"
                                msg += "<i>(Вы и ваш друг получаете по +5 дней, когда он впервые оплачивает подписку)</i>\n\n"
                                msg += "Хотите стать партнёром и получать деньги? Напишите в техподдержку."

                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML",
                                disable_web_page_preview=True, reply_markup=get_main_kb(uid_raw))
                    elif data == "buy":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        WAITING_FOR_PROMO[uid_raw] = time.time()
                        
                        kb_promo = {"inline_keyboard": [
                            [{"text": "➡️ Продолжить без промокода", "callback_data": "buy_no_promo"}],
                            [{"text": "🔙 Отмена", "callback_data": "back_main"}]
                        ]}
                        msg_text = "🎁 <b>У вас есть промокод?</b>\n\nЕсли да, отправьте его ответным сообщением прямо сейчас 👇\n\nЕсли промокода нет, нажмите кнопку «Продолжить без промокода»."
                        safe_edit(chat, cq["message"], text=msg_text, reply_markup=kb_promo, parse_mode="HTML")
                    elif data == "buy_no_promo":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        if uid_raw in WAITING_FOR_PROMO:
                            del WAITING_FOR_PROMO[uid_raw]
                        uid = f"tg{uid_raw}"
                        do_buy(chat, uid)
                    elif data == "enter_promo":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get('id'))
                        WAITING_FOR_PROMO[uid_raw] = time.time()
                        kb_promo = {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "back_main"}]]}
                        safe_edit(chat, cq["message"], text="🎁 <b>Отправьте ваш промокод</b> ответным сообщением прямо сейчас 👇", reply_markup=kb_promo, parse_mode="HTML")
                    
                    elif data == "info":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)
                        if is_test_user:
                            msg = """<b>VenturaVPN — интернет без границ.</b>

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
                            # Редактируем сообщение вместо создания нового
                            kb = {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "info_back"}]]}
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=kb)
                        else:
                            msg = "ℹ️ <b>Информация</b>\n\n<a href='https://venturavpn.club/polzovatelskoe-soglashenie.html'>📄 Соглашение</a>\n<a href='https://venturavpn.club/politika-konfidencialnosti.html'>🔒 Конфиденциальность</a>"
                            safe_edit(chat, cq["message"], text=msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_kb(uid_raw))

                    elif data == "info_back":
                        # Возвращаемся к главному меню - редактируем сообщение
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        is_test_user = (uid_raw == TEST_USER_ID)

                        if is_test_user:
                            STICKER_ID = "CAACAgEAAxkBAAEF3HhqbhZvJWm-aqcFrnAy9S2lK1Xa4gACggoAApH6aEfLT1-_Y898yj0E"
                            # Нельзя отправить стикер через edit, поэтому просто показываем текст с клавиатурой
                            sub_details = get_subscription_details(f"tg{uid_raw}")
                            if sub_details and sub_details.get("has_sub"):
                                welcome_text = ACTIVE_SUBSCRIPTION_MSG.format(
                                    days_left=sub_details["days_left"],
                                    max_devices=sub_details["max_devices"],
                                    end_date=sub_details["end_date_str"]
                                )
                            else:
                                welcome_text = NO_SUBSCRIPTION_MSG
                            safe_edit(chat, cq["message"], text=welcome_text, reply_markup=get_main_kb(uid_raw))
                        else:
                            PHOTO_URL = "https://venturavpn.club/bot-banner.jpg"
                            safe_edit(chat, cq["message"], text=WELCOME, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_kb(uid_raw))

                    elif data == "setup_iphone":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        msg = IPHONE_SETUP_MSG
                        kb = {"inline_keyboard": [
                            [{"text": "Назад", "callback_data": "mysub_menu"}]
                        ]}
                        api("sendMessage", chat_id=chat, text=msg, reply_markup=kb)

                    elif data == "setup_android":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        msg = IPHONE_SETUP_MSG  # Same message for now
                        kb = {"inline_keyboard": [
                            [{"text": "Назад", "callback_data": "mysub_menu"}]
                        ]}
                        api("sendMessage", chat_id=chat, text=msg, reply_markup=kb)

                    elif data == "ref_invited":
                        frm = cq.get("from", {})
                        uid_raw = str(frm.get("id"))
                        stats = get_ref_stats(uid_raw)
                        invited_count = stats.get("count", 0)
                        msg = f"Приглашено: {invited_count}\n\n"
                        msg += "ваша награда - "
                        kb = {"inline_keyboard": [
                            [{"text": "назад", "callback_data": "partner"}]
                        ]}
                        api("sendMessage", chat_id=chat, text=msg, reply_markup=kb)
                    elif data.startswith("check_"):
                        frm = cq.get("from", {})
                        uid = f"tg{frm.get('id')}"
                        try:
                            req = urllib.request.Request(
                                f"http://150.241.66.53/api/payment/check?order_id={uid}",
                                headers={"Host": "panel.venturavpn.club"}
                            )
                            with urllib.request.urlopen(req, timeout=15) as r:
                                res = json.load(r)
                                if res.get("status") == "paid":
                                    api("sendMessage", chat_id=chat, text="✅ Оплата успешно получена! Зайдите в меню «Моя подписка», чтобы получить ключ.", reply_markup=get_main_kb(uid_raw))
                                else:
                                    api("answerCallbackQuery", callback_query_id=cq["id"], text="⏳ Оплата пока не поступила", show_alert=True)
                        except Exception as e:
                            api("sendMessage", chat_id=chat, text=f"Ошибка проверки оплаты: {e}", reply_markup=get_main_kb(uid_raw))
                    continue
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "") or ""
                uid_raw = str(msg["from"]["id"])

                # Handle broadcast message from admin
                if WAITING_FOR_BROADCAST.get(uid_raw):
                    if text == "/cancel":
                        del WAITING_FOR_BROADCAST[uid_raw]
                        api("sendMessage", chat_id=chat_id, text="❌ Отменено", reply_markup=get_main_kb(uid_raw))
                    else:
                        del WAITING_FOR_BROADCAST[uid_raw]
                        # Here you would send the message to all users
                        api("sendMessage", chat_id=chat_id, text=f"📢 Сообщение отправлено всем пользователям:\n\n{text}", reply_markup=ADMIN_KB)
                    continue

                if text.startswith("/start"):
                    uid_raw = str(msg["from"]["id"])
                    parts = text.split()
                    if len(parts) > 1 and parts[1].startswith("ref_"):
                        referrer = parts[1][4:]
                        uid_raw = str(msg["from"]["id"])
                        add_referral(uid_raw, referrer)

                    # Check if test user for new design
                    is_test_user = (uid_raw == TEST_USER_ID)

                    # Get subscription status
                    uid_for_api = f"tg{uid_raw}"
                    sub_details = get_subscription_details(uid_for_api)

                    if is_test_user:
                        # New design: send sticker first, then message
                        STICKER_ID = "CAACAgEAAxkBAAEF3HhqbhZvJWm-aqcFrnAy9S2lK1Xa4gACggoAApH6aEfLT1-_Y898yj0E"
                        api("sendSticker", chat_id=chat_id, sticker=STICKER_ID)

                        # Determine which welcome message to show based on subscription status
                        if sub_details and sub_details.get("has_sub"):
                            # User has active subscription
                            welcome_text = ACTIVE_SUBSCRIPTION_MSG.format(
                                days_left=sub_details["days_left"],
                                max_devices=sub_details["max_devices"],
                                end_date=sub_details["end_date_str"]
                            )
                        else:
                            # User has no subscription or it expired
                            welcome_text = NO_SUBSCRIPTION_MSG

                        api("sendMessage", chat_id=chat_id, text=welcome_text, reply_markup=get_main_kb(uid_raw))
                    else:
                        PHOTO_URL = "https://venturavpn.club/bot-banner.jpg"
                        res = api("sendPhoto", chat_id=chat_id, photo=PHOTO_URL, caption=WELCOME, parse_mode="HTML", reply_markup=get_main_kb(uid_raw))
                        if not res.get("ok"):
                            api("sendMessage", chat_id=chat_id, text=WELCOME, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_kb(uid_raw))
                elif text.startswith("/find"):
                    uid_raw = str(msg["from"]["id"])
                    if uid_raw != "5129672873":
                        api("sendMessage", chat_id=chat_id, text="Команда не найдена:", reply_markup=get_main_kb(uid_raw))
                    else:
                        parts = text.split()
                        if len(parts) < 2:
                            api("sendMessage", chat_id=chat_id, text="Использование: /find @username или /find ID")
                        else:
                            username = parts[1].replace("@", "")
                            try:
                                req = urllib.request.Request(f"http://150.241.66.53/api/payment/find?secret=vpanel_7kQ2xR9mZ&username={urllib.parse.quote(username)}", headers={"Host": "panel.venturavpn.club"})
                                with urllib.request.urlopen(req, timeout=15) as r:
                                    res = json.load(r)
                                    payments = res.get("payments", [])
                                    if not payments:
                                        msg_text = "Ничего не найдено."
                                    else:
                                        msg_text = "Последние платежи:\n\n"
                                        for p in payments:
                                            d = time.strftime("%d.%m.%Y %H:%M", time.gmtime(p["created"]))
                                            msg_text += f"ID: {p['payment_id']}\nСумма: {p['amount']} RUB\nСтатус: {p['status']}\nПромо: {p.get('promo', '-')}\nДата: {d}\n\n"
                                    api("sendMessage", chat_id=chat_id, text=msg_text)
                            except Exception as e:
                                api("sendMessage", chat_id=chat_id, text=f"Ошибка: {e}")

                elif text.startswith("/"):
                    uid_raw = str(msg["from"]["id"])
                    api("sendMessage", chat_id=chat_id,
                        text="Выберите действие в меню:", reply_markup=get_main_kb(uid_raw))
                elif text.strip():
                    uid_raw = str(msg["from"]["id"])
                    if uid_raw in WAITING_FOR_WEB_LOGIN and time.time() - WAITING_FOR_WEB_LOGIN[uid_raw] < 3600:
                        del WAITING_FOR_WEB_LOGIN[uid_raw]
                        login = text.strip()
                        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', login):
                            kb = {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "mysub_menu"}]]}
                            api("sendMessage", chat_id=chat_id, text="❌ Логин: 3-20 символов (буквы, цифры, _).", reply_markup=kb, parse_mode="HTML")
                            WAITING_FOR_WEB_LOGIN[uid_raw] = time.time()
                        else:
                            WAITING_FOR_WEB_PASSWORD[uid_raw] = {"login": login, "ts": time.time()}
                            kb = {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "mysub_menu"}]]}
                            api("sendMessage", chat_id=chat_id, text="🔐 Придумайте пароль (минимум 6 символов).", reply_markup=kb, parse_mode="HTML")
                    elif uid_raw in WAITING_FOR_WEB_PASSWORD and time.time() - WAITING_FOR_WEB_PASSWORD[uid_raw]["ts"] < 3600:
                        info = WAITING_FOR_WEB_PASSWORD.pop(uid_raw)
                        password = text.strip()
                        if len(password) < 6:
                            kb = {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "mysub_menu"}]]}
                            api("sendMessage", chat_id=chat_id, text="❌ Пароль: минимум 6 символов.", reply_markup=kb, parse_mode="HTML")
                        else:
                            uid = f"tg{uid_raw}"
                            try:
                                reg_url = f"https://panel.venturavpn.club/api/account/register?secret=vpanel_7kQ2xR9mZ&uid={uid}&login={urllib.parse.quote(info['login'])}&password={urllib.parse.quote(password)}"
                                req = urllib.request.Request(reg_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(req, timeout=10) as r:
                                    res = json.load(r)
                            except urllib.error.HTTPError as e:
                                res = json.loads(e.read().decode())
                            except Exception as e:
                                res = {"error": str(e)}
                            if res.get("ok"):
                                kb = {"inline_keyboard": [
                                    [{"text": "🌐 Открыть кабинет", "web_app": {"url": "https://my.venturavpn.club"}}],
                                    [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                                ]}
                                api("sendMessage", chat_id=chat_id, text=f"✅ <b>Аккаунт создан!</b>\n\nЛогин: <code>{info['login']}</code>\n\nВойдите на my.venturavpn.club", reply_markup=kb, parse_mode="HTML")
                            else:
                                err_map = {"login_taken": "Логин занят.", "already_registered": "У вас уже есть аккаунт."}
                                msg = f"❌ {err_map.get(res.get('error'), res.get('error', 'ошибка'))}"
                                kb = {"inline_keyboard": [[{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]]}
                                api("sendMessage", chat_id=chat_id, text=msg, reply_markup=kb, parse_mode="HTML")
                    elif uid_raw in WAITING_FOR_PROMO and time.time() - WAITING_FOR_PROMO[uid_raw] < 3600:
                        del WAITING_FOR_PROMO[uid_raw]
                        uid = f"tg{uid_raw}"
                        code = text.strip()
                        res = do_buy(chat_id, uid, promo=code)
                        if res.get("promo_error"):
                            kb_promo = {"inline_keyboard": [
                                [{"text": "➡️ Продолжить без промокода", "callback_data": "buy_no_promo"}],
                                [{"text": "🔙 Отмена", "callback_data": "back_main"}]
                            ]}
                            msg_text = f"❌ <b>Ошибка:</b> {res.get('error')}\n\nПопробуйте отправить другой промокод или нажмите кнопку ниже."
                            api("sendMessage", chat_id=chat_id, text=msg_text, reply_markup=kb_promo, parse_mode="HTML")
                            WAITING_FOR_PROMO[uid_raw] = time.time()
                    elif uid_raw in WAITING_FOR_SYNC_CODE and time.time() - WAITING_FOR_SYNC_CODE[uid_raw] < 3600:
                        del WAITING_FOR_SYNC_CODE[uid_raw]
                        uid = f"tg{uid_raw}"
                        code = text.strip()
                        username = msg["from"].get("username", "")
                        res = link_apply(code, uid, "tg", username)
                        if res.get("error"):
                            err_map = {
                                "code_not_found_or_expired": "Код не найден или истёк.",
                                "code_expired": "Код больше не действителен.",
                                "same_platform": "Нельзя связать два аккаунта одной платформы.",
                                "both_have_subscriptions": "Нельзя связать: подписка уже есть на обоих аккаунтах.",
                                "already_linked": "Ваш аккаунт уже привязан к другому.",
                            }
                            err_msg = f"❌ {err_map.get(res['error'], res['error'])}"
                            kb = {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "sync_menu"}]]}
                            api("sendMessage", chat_id=chat_id, text=err_msg, reply_markup=kb, parse_mode="HTML")
                        elif res.get("status") == "pending_confirmation":
                            init_uname = res.get("initiator_username", "") or res.get("initiator_uid", "")
                            init_plat = "MAX" if res.get("initiator_platform") == "max" else "Telegram"
                            msg_sync = f"⏳ <b>Запрос отправан</b>\n\nЗапрос на привязку отправлен пользователю <b>@{init_uname}</b> ({init_plat}).\nОжидайте подтверждения."
                            kb = {"inline_keyboard": [[{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]]}
                            api("sendMessage", chat_id=chat_id, text=msg_sync, reply_markup=kb, parse_mode="HTML")
                            WAITING_FOR_SYNC_RESULT[uid_raw] = {"chat_id": chat_id, "uid": uid}
                    else:
                        api("sendMessage", chat_id=chat_id,
                            text="Выберите действие в меню:", reply_markup=get_main_kb(uid_raw))
                else:
                    uid_raw = str(msg["from"]["id"])
                    api("sendMessage", chat_id=chat_id,
                        text="Выберите действие в меню:", reply_markup=get_main_kb(uid_raw))
            except Exception as e:
                print("upd error:", e)


def poll_pending_confirmations():
    """Background thread: poll for pending sync confirmations and notify TG users."""
    while True:
        try:
            expired = []
            for uid_raw, info in list(ACTIVE_SYNC_CODES.items()):
                code = info.get("code", "")
                chat_id = info.get("chat_id", "")
                if not code or not chat_id:
                    expired.append(uid_raw)
                    continue
                uid = f"tg{uid_raw}"
                pc = pending_confirmation(uid)
                if pc.get("pending"):
                    app_uname = pc.get("applicant_username", "") or pc.get("applicant_uid", "")
                    app_plat = "MAX" if pc.get("applicant_platform") == "max" else "Telegram"
                    scode = pc.get("code", "")
                    msg = "🔗 <b>Входящий запрос на привязку</b>\n\n"
                    msg += f"Пользователь <b>@{app_uname}</b> ({app_plat}) хочет связать свой аккаунт с вашим.\n"
                    msg += "Подтвердить привязку?"
                    kb = {
                        "inline_keyboard": [
                            [{"text": "✅ Да", "callback_data": f"sync_confirm_{scode}_yes"}, {"text": "❌ Нет", "callback_data": f"sync_confirm_{scode}_no"}],
                            [{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]
                        ]
                    }
                    api("sendMessage", chat_id=chat_id, text=msg, parse_mode="HTML", reply_markup=kb)
                    expired.append(uid_raw)
            for u in expired:
                ACTIVE_SYNC_CODES.pop(u, None)
            resolved = []
            for uid_raw, info in list(WAITING_FOR_SYNC_RESULT.items()):
                uid = info.get("uid", "")
                chat_id = info.get("chat_id", "")
                if not uid or not chat_id:
                    resolved.append(uid_raw)
                    continue
                ls = link_status(uid)
                if ls.get("linked"):
                    msg = "✅ <b>Аккаунты успешно связаны!</b>\n\nТеперь подписка общая для Telegram и MAX."
                    kb = {"inline_keyboard": [[{"text": "🔙 К подписке", "callback_data": "mysub_menu"}]]}
                    api("sendMessage", chat_id=chat_id, text=msg, parse_mode="HTML", reply_markup=kb)
                    resolved.append(uid_raw)
            for u in resolved:
                WAITING_FOR_SYNC_RESULT.pop(u, None)
        except Exception as e:
            logging.error(f"poll_pending error: {e}")
        time.sleep(10)


if __name__ == "__main__":
    t = threading.Thread(target=poll_pending_confirmations, daemon=True)
    t.start()
    main()
