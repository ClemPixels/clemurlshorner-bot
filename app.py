import os
import string
from urllib.parse import urlparse

import asyncpg
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------------
# Config
# -------------------------
DB_URL = os.environ.get("DATABASE_URL")  # Neon connection string
BASE_URL = os.environ.get("BASE_URL")  # change for production
ALPHABET = string.digits + string.ascii_letters


# -------------------------
# DB helpers
# -------------------------
async def get_db():
    return await asyncpg.connect(DB_URL)


async def init_db():
    conn = await get_db()
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            long_url TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.close()


# -------------------------
# Base62 encode
# -------------------------
def base62_encode(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    out = []
    base = len(ALPHABET)
    while n:
        n, r = divmod(n, base)
        out.append(ALPHABET[r])
    return "".join(reversed(out))


# -------------------------
# URL validation
# -------------------------
def is_valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


# -------------------------
# Shortener logic
# -------------------------
async def shorten_url(long_url: str) -> str:
    conn = await get_db()
    row = await conn.fetchrow("SELECT code FROM urls WHERE long_url = $1", long_url)
    if row:
        code = row["code"]
    else:
        new_id = await conn.fetchval(
            "INSERT INTO urls (long_url) VALUES ($1) RETURNING id", long_url
        )
        code = base62_encode(new_id)
        await conn.execute("UPDATE urls SET code = $1 WHERE id = $2", code, new_id)
    await conn.close()
    return f"{BASE_URL}/{code}"


# -------------------------
# Telegram bot handlers
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "👋 Hi! Send me any URL and I’ll shorten it for you."
        )

async def shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not is_valid_url(text):
        await update.message.reply_text("❌ Please send a valid http/https URL.")
        return

    short = await shorten_url(text)
    await update.message.reply_text(f"✅ Shortened link: {short}")
    await update.message.reply_text(f"✅ Shortened link: {short}")


# -------------------------
# Main entry
# -------------------------
async def main():
    await init_db()
    token = os.environ.get("BOT_TOKEN") or "YOUR_FALLBACK_BOT_TOKEN"
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten))

    print("🤖 Bot is running...")
    await app.run_polling()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
