import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
from aiohttp import web

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN         = os.getenv("BOT_TOKEN")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
SPREADSHEET_ID    = os.getenv("SPREADSHEET_ID")
OWNER_CHAT_ID     = os.getenv("OWNER_CHAT_ID")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
WEBHOOK_URL       = os.getenv("WEBHOOK_URL", "")

# ─── СОСТОЯНИЯ ──────────────────────────────────────────
(
    MAIN_MENU,
    AI_CHAT,
    BOOKING_NAME,
    BOOKING_PHONE,
    BOOKING_DATE,
    BOOKING_TIME,
    BOOKING_HALL,
    BOOKING_CONFIRM,
) = range(8)

# ─── ИНФО О РЕСТОРАНЕ ───────────────────────────────────
RESTAURANT_INFO = """
Банкетный ресторан АЙСАФИ
Адрес: Наурызбай батыра 22

ЗАЛЫ:
- Premium Hall — до 220 персон
- Benefis Hall — до 100 персон
- VIP Hall — до 50 персон

ПАКЕТЫ:
Пакет 1 — 16 000 тенге/персона:
  • 4 вида салата
  • 2 холодных закуски
  • Бешбармак
  • Второе горячее

Пакет 2 — 14 000 тенге/персона:
  • 3 вида салата
  • 2 холодных закуски
  • Бешбармак
  • Второе горячее

Салаты, закуски и горячее от ресторана.
Мясо на бешбармак и чайный стол от владельца банкета.
Проводим: свадьбы, тои, узату, корпоративы, юбилеи.
"""

SYSTEM_PROMPT = f"""Ты вежливый и профессиональный AI-менеджер банкетного ресторана АЙСАФИ.

{RESTAURANT_INFO}

ТВОИ ЗАДАЧИ:
1. Консультировать гостей по залам, пакетам, ценам
2. Помогать выбрать зал исходя из количества гостей
3. Рассчитывать стоимость (количество гостей умножить на цену пакета)
4. Отвечать на вопросы о меню и условиях
5. Предлагать записаться на живую консультацию

ПРАВИЛА:
- Отвечай тепло и гостеприимно
- Используй эмодзи умеренно
- Отвечай на русском, на казахском если гость пишет по-казахски
- Будь краток но информативен
- Если гость хочет записаться скажи что нужно нажать кнопку Записаться на консультацию
"""

# ─── GOOGLE SHEETS ───────────────────────────────────────

def save_to_sheets(data: dict):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        if not sheet.row_values(1):
            sheet.append_row(["Дата записи", "Имя", "Телефон", "Дата консультации", "Время", "Зал", "Статус"])
        sheet.append_row([
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            data.get("name", ""),
            data.get("phone", ""),
            data.get("date", ""),
            data.get("time", ""),
            data.get("hall", ""),
            "Новая заявка"
        ])
        return True
    except Exception as e:
        logger.error(f"Sheets error: {e}")
        return False

# ─── KEYBOARDS ───────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Задать вопрос", callback_data="ai_chat")],
        [InlineKeyboardButton("📋 Залы и пакеты", callback_data="show_info")],
        [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="start_booking")],
        [InlineKeyboardButton("📍 Адрес и контакты", callback_data="contacts")],
    ])

def hall_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Premium Hall (до 220 чел.)", callback_data="hall_premium")],
        [InlineKeyboardButton("🌟 Benefis Hall (до 100 чел.)", callback_data="hall_benefis")],
        [InlineKeyboardButton("💎 VIP Hall (до 50 чел.)", callback_data="hall_vip")],
    ])

def time_keyboard():
    times = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    rows = []
    row = []
    for i, t in enumerate(times):
        row.append(InlineKeyboardButton(t, callback_data=f"time_{t}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]])

# ─── HANDLERS ────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = (
        "🎊 *Добро пожаловать в банкетный ресторан АЙСАФИ!*\n\n"
        "Организуем незабываемые торжества.\n\n"
        "👑 Premium Hall — до 220 персон\n"
        "🌟 Benefis Hall — до 100 персон\n"
        "💎 VIP Hall — до 50 персон\n\n"
        "Чем могу помочь?"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    return MAIN_MENU

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "🏛 *Залы АЙСАФИ:*\n\n"
        "👑 *Premium Hall* — до 220 персон\n"
        "🌟 *Benefis Hall* — до 100 персон\n"
        "💎 *VIP Hall* — до 50 персон\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🍽 *Пакет 1 — 16 000 тг/персона:*\n"
        "• 4 вида салата\n"
        "• 2 холодных закуски\n"
        "• Бешбармак\n"
        "• Второе горячее\n\n"
        "🍽 *Пакет 2 — 14 000 тг/персона:*\n"
        "• 3 вида салата\n"
        "• 2 холодных закуски\n"
        "• Бешбармак\n"
        "• Второе горячее\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "_Салаты, закуски и горячее от ресторана._\n"
        "_Мясо на бешбармак и чайный стол от вас._"
    )
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Задать вопрос", callback_data="ai_chat")],
        [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="start_booking")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ]))
    return MAIN_MENU

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📍 *АЙСАФИ — контакты:*\n\n"
        "🗺 Адрес: *Наурызбай батыра 22*\n"
        "🕐 Работаем: 9:00 — 22:00\n\n"
        "[📍 Открыть на 2GIS](https://2gis.kz/search/Наурызбай%20батыра%2022)",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
        disable_web_page_preview=True
    )
    return MAIN_MENU

# ─── AI CHAT ─────────────────────────────────────────────

async def ai_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["chat_history"] = []
    await q.edit_message_text(
        "💬 *Спросите что угодно об АЙСАФИ*\n\n"
        "_Например: сколько стоит зал на 150 человек?_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="start_booking")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ])
    )
    return AI_CHAT

async def ai_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    history = context.user_data.get("chat_history", [])
    msg = await update.message.reply_text("⏳ Думаю...")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-10:]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.5,
            max_tokens=800,
        )
        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        context.user_data["chat_history"] = history
        await msg.edit_text(answer, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="start_booking")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ]))
    except Exception as e:
        logger.error(f"AI error: {e}")
        await msg.edit_text("Извините, ошибка. Попробуйте ещё раз.", reply_markup=back_keyboard())
    return AI_CHAT

# ─── BOOKING ─────────────────────────────────────────────

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["booking"] = {}
    await q.edit_message_text(
        "📅 *Запись на консультацию*\n\nШаг 1/5 — Введите ваше *имя:*",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return BOOKING_NAME

async def booking_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["booking"]["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📱 Шаг 2/5 — Введите *номер телефона:*",
        parse_mode="Markdown", reply_markup=cancel_keyboard()
    )
    return BOOKING_PHONE

async def booking_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["booking"]["phone"] = update.message.text.strip()
    await update.message.reply_text(
        "📆 Шаг 3/5 — Введите *дату консультации*\n_(например: 25.03.2026)_",
        parse_mode="Markdown", reply_markup=cancel_keyboard()
    )
    return BOOKING_DATE

async def booking_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["booking"]["date"] = update.message.text.strip()
    await update.message.reply_text(
        "🕐 Шаг 4/5 — Выберите *удобное время:*",
        parse_mode="Markdown", reply_markup=time_keyboard()
    )
    return BOOKING_TIME

async def booking_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["booking"]["time"] = q.data.replace("time_", "")
    await q.edit_message_text(
        "🏛 Шаг 5/5 — Выберите *интересующий зал:*",
        parse_mode="Markdown", reply_markup=hall_keyboard()
    )
    return BOOKING_HALL

async def booking_hall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    hall_map = {
        "hall_premium": "👑 Premium Hall (до 220 чел.)",
        "hall_benefis": "🌟 Benefis Hall (до 100 чел.)",
        "hall_vip":     "💎 VIP Hall (до 50 чел.)",
    }
    context.user_data["booking"]["hall"] = hall_map.get(q.data, q.data)
    b = context.user_data["booking"]
    await q.edit_message_text(
        f"✅ *Проверьте данные:*\n\n"
        f"👤 Имя: *{b['name']}*\n"
        f"📱 Телефон: *{b['phone']}*\n"
        f"📆 Дата: *{b['date']}*\n"
        f"🕐 Время: *{b['time']}*\n"
        f"🏛 Зал: *{b['hall']}*\n\nВсё верно?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")],
            [InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")],
        ])
    )
    return BOOKING_CONFIRM

async def booking_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "confirm_no":
        await q.edit_message_text("❌ Запись отменена.", reply_markup=back_keyboard())
        return MAIN_MENU
    b = context.user_data["booking"]
    saved = save_to_sheets(b) if SPREADSHEET_ID else False
    if OWNER_CHAT_ID:
        try:
            await q.get_bot().send_message(
                chat_id=OWNER_CHAT_ID,
                text=(
                    f"🔔 *Новая запись на консультацию!*\n\n"
                    f"👤 {b['name']}\n"
                    f"📱 {b['phone']}\n"
                    f"📆 {b['date']} в {b['time']}\n"
                    f"🏛 {b['hall']}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Owner notify error: {e}")
    sheets_note = "\n✅ Запись сохранена в таблице." if saved else ""
    await q.edit_message_text(
        f"🎉 *Запись подтверждена!*\n\n"
        f"Ждём вас {b['date']} в {b['time']}.\n"
        f"Адрес: Наурызбай батыра 22\n\n"
        f"Менеджер свяжется с вами по номеру *{b['phone']}*{sheets_note}",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    return MAIN_MENU

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено. /start", reply_markup=main_keyboard())
    return MAIN_MENU

# ─── WEBHOOK ─────────────────────────────────────────────

async def health(request):
    return web.Response(text="OK")

async def webhook_handler(request):
    ptb = request.app["ptb_app"]
    data = await request.json()
    update = Update.de_json(data, ptb.bot)
    await ptb.process_update(update)
    return web.Response(text="ok")

async def on_startup(aio_app):
    ptb = aio_app["ptb_app"]
    await ptb.initialize()
    await ptb.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", allowed_updates=Update.ALL_TYPES)
    await ptb.start()
    logger.info(f"Webhook: {WEBHOOK_URL}/webhook")

async def on_shutdown(aio_app):
    ptb = aio_app["ptb_app"]
    await ptb.bot.delete_webhook()
    await ptb.stop()
    await ptb.shutdown()

# ─── MAIN ────────────────────────────────────────────────

def build_app(use_webhook: bool):
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не задан в .env")

    if use_webhook:
        app = Application.builder().token(BOT_TOKEN).updater(None).build()
    else:
        app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(show_info,          pattern="^show_info$"),
                CallbackQueryHandler(contacts,           pattern="^contacts$"),
                CallbackQueryHandler(ai_chat_start,      pattern="^ai_chat$"),
                CallbackQueryHandler(start_booking,      pattern="^start_booking$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            AI_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_message),
                CallbackQueryHandler(start_booking,      pattern="^start_booking$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_name),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_phone),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_date),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_TIME: [
                CallbackQueryHandler(booking_time, pattern="^time_"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_HALL: [
                CallbackQueryHandler(booking_hall, pattern="^hall_"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
            BOOKING_CONFIRM: [
                CallbackQueryHandler(booking_confirm, pattern="^confirm_"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
    return app


def main():
    use_webhook = bool(WEBHOOK_URL)

    if use_webhook:
        logger.info(f"Webhook: {WEBHOOK_URL}")
        aio_app = web.Application()
        aio_app["ptb_app"] = build_app(use_webhook=True)
        aio_app.router.add_get("/",        health)
        aio_app.router.add_get("/health",  health)
        aio_app.router.add_post("/webhook", webhook_handler)
        aio_app.on_startup.append(on_startup)
        aio_app.on_shutdown.append(on_shutdown)
        port = int(os.getenv("PORT", 8080))
        logger.info(f"Бот АЙСАФИ запущен на порту {port}")
        web.run_app(aio_app, host="0.0.0.0", port=port)
    else:
        logger.info("Polling режим (локальный тест)")
        app = build_app(use_webhook=False)
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
