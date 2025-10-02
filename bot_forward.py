import os
import logging
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ChatMember, ChatMemberUpdated, BotCommand
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    ChatMemberHandler, MessageHandler, filters
)

# Config  
TOKEN = os.getenv("TELEGRAM_BOTTOKEN")
GROUPCHATID = int(os.getenv("GROUPCHATID", "0"))
PORT = int(os.getenv("PORT", "8080"))
CHECK_INTERVAL = 30 * 60  # 30 minuti

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOTTOKEN non trovato nelle ENV")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Memoria dei canali per gruppo e last message_id
group_channels: dict[int, str] = {}
last_ids: dict[str, int] = {}

# Health check HTTP server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        return  # disabilita log default

def run_http_server():
    httpd = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"Health endpoint listening on 0.0.0.0:{PORT}")
    httpd.serve_forever()

# Handler /start (in chat privato)
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot avviato! Aggiungimi in un gruppo per configurare il canale delle notizie."
    )

# Quando il bot viene aggiunto a un gruppo
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = update.chat_member.new_chat_member.status
    if update.chat_member.new_chat_member.user.is_bot and status in ("member", "administrator"):
        await update.effective_chat.send_message(
            "Per favore, scrivete l'username del canale da cui ricevere le notizie ogni 30 minuti (es. @nomecanale)."
        )

# Gestione della risposta con l’username del canale
async def handle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    if text.startswith("@"):
        channel = text[1:]
        group_channels[chat_id] = channel
        last_ids.setdefault(channel, 0)
        await update.message.reply_text(f"Canale impostato su @{channel}.")
        logger.info(f"Gruppo {chat_id} → canale {channel}")
    else:
        await update.message.reply_text("Formato non valido. Scrivi @nomecanale.")

# Job ricorrente per inoltrare le notizie
async def forward_job(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    for group_id, channel in group_channels.items():
        last_id = last_ids.get(channel, 0)
        # Legge ultimi 10 messaggi dal canale
        history = await bot.get_chat_history(chat_id=f"@{channel}", limit=10)
        for msg in reversed(history):
            if msg.message_id > last_id:
                await bot.forward_message(
                    chat_id=group_id,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )
                last_ids[channel] = msg.message_id

def main():
    application = Application.builder().token(TOKEN).build()

    # Registra comando /start e aiuta Telegram a mostrarlo
    application.bot.set_my_commands([BotCommand("start", "Avvia il bot")])

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel)
    )

    # JobQueue per forwarding
    jq = application.job_queue
    jq.run_repeating(forward_job, interval=CHECK_INTERVAL, first=10)

    # Avvio thread HTTP server
    threading.Thread(target=run_http_server, daemon=True).start()

    # Avvia polling (unico getUpdates)
    application.run_polling()

if __name__ == "__main__":
    main()
