import os
import logging
import asyncio
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import (
    Application, ContextTypes, CommandHandler, ChatMemberHandler, MessageHandler, filters
)
from dotenv import load_dotenv
import threading

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOTTOKEN")
CHECKINTERVAL = 30 * 60  # 30 minutes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Memoria dei canali selezionati per gruppo {group_chat_id: channel_username}
group_channels = {}

lastupdateid_per_channel = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot di forwarding avviato! Invita il bot in un gruppo e seleziona il canale per le notizie."
    )

async def ask_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ciao! Per favore, indicami il nome utente (username) del canale da cui vuoi ricevere le ultime notizie ogni 30 minuti.\n"
        "Scrivi @nomecanale"
    )

async def handle_channel_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    if text.startswith("@"):
        group_channels[chat_id] = text[1:]  # togliere @
        lastupdateid_per_channel[group_channels[chat_id]] = 0
        await update.message.reply_text(f"Canale impostato su @{group_channels[chat_id]}, inizierò a inviare le notizie ogni 30 minuti.")
        logger.info(f"Gruppo {chat_id} impostato per canale {group_channels[chat_id]}")
    else:
        await update.message.reply_text("Formato non valido. Per favore, scrivi l'username del canale iniziando con '@'.")

async def check_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member_update: ChatMemberUpdated = update.chat_member
    new_member: ChatMember = chat_member_update.new_chat_member
    if new_member.user.is_bot and new_member.status in ("member", "administrator"):
        # Bot appena aggiunto al gruppo
        await ask_channel(update, context)

async def forwardloop(application: Application):
    while True:
        try:
            bot = application.bot
            for group_id, channel_username in group_channels.items():
                last_update_id = lastupdateid_per_channel.get(channel_username, 0)
                updates = await bot.get_updates(offset=last_update_id + 1, timeout=10)
                for u in updates:
                    lastupdateid_per_channel[channel_username] = u.update_id
                    if u.channel_post and u.channel_post.chat.username == channel_username:
                        await bot.forward_message(chat_id=group_id, from_chat_id=u.channel_post.chat.id, message_id=u.channel_post.message_id)
            await asyncio.sleep(CHECKINTERVAL)
        except Exception as e:
            logger.error(f"Errore nel loop forwarding: {e}")
            await asyncio.sleep(CHECKINTERVAL)

def start_forwarding(application):
    asyncio.run(forwardloop(application))

def main():
    application = Application.builder().token(TOKEN).build()

    # Comando /start
    application.add_handler(CommandHandler("start", start))

    # Rilevare aggiunta bot al gruppo
    application.add_handler(ChatMemberHandler(check_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

    # Gestire messaggi come risposta canale
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_response))

    threading.Thread(target=start_forwarding, args=(application,), daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()
