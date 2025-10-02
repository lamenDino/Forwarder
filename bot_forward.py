import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ChatMemberUpdated, BotCommand
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    ChatMemberHandler, filters
)

# Configurazione
TOKEN = os.getenv("TELEGRAM_BOTTOKEN")
PORT = int(os.getenv("PORT", "8080"))
CHECK_INTERVAL = 60  # 30 minuti

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOTTOKEN non trovato nelle ENV")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stato
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
        return

def run_http_server():
    httpd = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"Health endpoint listening on 0.0.0.0:{PORT}")
    httpd.serve_forever()

# /start in privato
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot avviato! Aggiungimi in un gruppo e usa /setcanale @nomeCanale per impostare il canale."
    )

# Bot aggiunto al gruppo
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chm: ChatMemberUpdated = update.chat_member
    if chm.new_chat_member.user.is_bot and chm.new_chat_member.status in ("member", "administrator"):
        await update.effective_chat.send_message(
            "Usa /setcanale @nomeCanale per impostare il canale da cui ricevere news ogni 30 minuti."
        )

# Controllo admin
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")

# /setcanale comando
async def set_canale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("Devi essere amministratore per usare questo comando.")
        return

    args = context.args
    if len(args) != 1 or not args[0].startswith("@"):
        await update.message.reply_text("Uso corretto: /setcanale @nomeCanale")
        return

    channel = args[0][1:]
    chat_id = update.effective_chat.id
    group_channels[chat_id] = channel
    last_ids.setdefault(channel, 0)
    await update.message.reply_text(f"Canale impostato su @{channel}.")
    logger.info(f"Gruppo {chat_id} → canale {channel}")

# Job ricorrente forwarding
async def forward_job(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    for group_id, channel in group_channels.items():
        last_id = last_ids.get(channel, 0)
        history = await bot.get_chat_history(chat_id=f"@{channel}", limit=10)
        for msg in reversed(history):
            if msg.message_id > last_id:
                await bot.forward_message(
                    chat_id=group_id,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )
                last_ids[channel] = msg.message_id
                logger.info(f"Inoltrato messaggio {msg.message_id} da @{channel} a gruppo {group_id}")

def main():
    async def set_commands(app: Application):
        await app.bot.set_my_commands([
            BotCommand("start", "Avvia il bot"),
            BotCommand("setcanale", "Imposta il canale da cui ricevere news")
        ])

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(set_commands)
        .build()
    )

    # Handler
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("setcanale", set_canale))
    application.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    # Rimuove handler generici: non registrare MessageHandler

    # JobQueue
    jq = application.job_queue
    jq.run_repeating(forward_job, interval=CHECK_INTERVAL, first=10)

    # HTTP health server
    threading.Thread(target=run_http_server, daemon=True).start()

    # Avvio polling
    application.run_polling()

if __name__ == "__main__":
    main()
