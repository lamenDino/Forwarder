#!/usr/bin/env python3
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_USERNAME = 'freegamesnot'
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))
CHECK_INTERVAL = 30 * 60  # 30 minuti

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

last_update_id = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot di forwarding avviato!")
    logger.info(f"Chat ID gruppo: {update.effective_chat.id}")

async def forward_loop(application: Application):
    global last_update_id
    bot = application.bot
    while True:
        try:
            updates = await bot.get_updates(offset=last_update_id + 1, timeout=10)
            for u in updates:
                last_update_id = u.update_id
                if u.channel_post and u.channel_post.chat.username == CHANNEL_USERNAME:
                    await bot.forward_message(
                        chat_id=GROUP_CHAT_ID,
                        from_chat_id=u.channel_post.chat.id,
                        message_id=u.channel_post.message_id
                    )
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Errore nel loop forwarding: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    # Avvia subito il forwarding loop
    application.job_queue.run_once(lambda ctx: asyncio.create_task(forward_loop(application)), when=0)
    application.run_polling()

if __name__ == '__main__':
    main()
