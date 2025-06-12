
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request
import threading
import uuid
import os
import requests
from pymongo import MongoClient
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
SHORTNER_API = os.getenv("SHORTNER_API")
BASE_VERIFY_URL = os.getenv("BASE_VERIFY_URL")  # Replace with your hosted Flask domain

client = MongoClient(MONGO_URL)
db = client["likebot"]
users = db["users"]

app = Flask(__name__)
verifications = {}

@app.route("/verify/<vid>")
def verify(vid):
    data = verifications.get(vid)
    if not data:
        return "Invalid or expired link"
    users.update_one({"user_id": data["user_id"]}, {"$set": {"verified": True, "uid": data["uid"]}}, upsert=True)
    return "Verification successful! Return to Telegram."

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def get_short_url(long_url):
    try:
        api_url = f"https://shortner.in/api?api={SHORTNER_API}&url={long_url}"
        res = requests.get(api_url).json()
        return res["shortenedUrl"] if res["status"] == "success" else long_url
    except:
        return long_url

LIKE_API = os.getenv("LIKE_API")

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    allowed_admins = os.getenv("ALLOWED_ADMINS", "").split(",")
    if str(update.effective_user.id) not in allowed_admins:
        await update.message.reply_text("🚫 You are not allowed to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /like <uid>")
        return
    uid = context.args[0]
    user_id = update.effective_user.id
    name = update.effective_user.full_name

    verify_id = str(uuid.uuid4())
    verifications[verify_id] = {"user_id": user_id, "uid": uid}

    long_url = f"{BASE_VERIFY_URL}{verify_id}"
    short_url = get_short_url(long_url)

    kb = [
        [InlineKeyboardButton("✅ VERIFY & SEND LIKE ✅", url=short_url)],
        [InlineKeyboardButton("❓ How to Verify ❓", callback_data="how_to")],
        [InlineKeyboardButton("😇 PURCHASE VIP & NO VERIFY", callback_data="vip")]
    ]
    markup = InlineKeyboardMarkup(kb)
    await update.message.reply_text(
        f"*Like Request*
👤 From: {name}
🆔 UID: `{uid}`
🌐 Region: IND
⚠️ Verify within 10 minutes",
        reply_markup=markup, parse_mode="Markdown"
    )

async def background_check(app):
    while True:
        for user in users.find({"verified": True, "like_sent": {"$ne": True}}):
            uid = user["uid"]
            user_id = user["user_id"]
            api_url = LIKE_API.format(uid=uid)
            res = requests.get(api_url).json()
            msg = (
                f"✅ *Request Processed Successfully*

"
                f"👤 Player: {res['name']}
🆔 UID: `{uid}`
🎖️ Level: {res['level']}
"
                f"🤡 Likes Before: {res['likes_before']}
📈 Likes Added: {res['likes_added']}
"
                f"🗿 Total Likes Now: {res['likes_after']}
⏰ Processed At: {res['processed_at']}"
            )
            await app.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
            users.update_one({"user_id": user_id}, {"$set": {"like_sent": True}})
        await asyncio.sleep(60)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("like", like_command))
    threading.Thread(target=run_flask).start()
    asyncio.create_task(background_check(application))
    application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
