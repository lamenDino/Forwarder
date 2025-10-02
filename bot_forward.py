import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ChatMemberUpdated, BotCommand
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    ChatMemberHandler, MessageHandler, filters
)

# Config
TOKEN = os.getenv("TELEGRAM_BOTTOKEN")
PORT = int(os.getenv("PORT", "8080"))

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOTTOKEN non trovato nelle ENV")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Mapping gruppo → canale
group_channel: dict[int, str] = {}

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
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

# /start in privato
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot attivo! Invita in un gruppo e usa /setcanale @nomeCanale."
    )

# Bot aggiunto al gruppo
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chm: ChatMemberUpdated = update.chat_member
    if (
        chm.new_chat_member.user.is_bot
        and chm.new_chat_member.status in ("member", "administrator")
    ):
        await update.effective_chat.send_message(
            "Usa /setcanale @nomeCanale per inoltrare post del canale al gruppo."
        )

# Controllo admin
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in ("administrator", "creator")

# /setcanale
async def set_canale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("Devi essere amministratore.")
        return

    args = context.args
    if len(args) != 1 or not args[0].startswith("@"):
        await update.message.reply_text("Uso: /setcanale @nomeCanale")
        return

    chan = args[0][1:]
    gid = update.effective_chat.id
    group_channel[gid] = chan
    await update.message.reply_text(f"Canale impostato su @{chan}.")
    logger.info(f"Gruppo {gid} → canale {chan}")

# Handler per post del canale
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chan = update.effective_chat.username
    for gid, target_chan in group_channel.items():
        if chan == target_chan:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            logger.info(
                f"Inoltrato post {update.message.message_id} da @{chan} a gruppo {gid}"
            )

def main():
    async def set_commands(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Avvia il bot"),
            BotCommand("setcanale", "Imposta il canale da inoltrare"),
        ])

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(set_commands)
        .build()
    )

    # Handler
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setcanale", set_canale))
    app.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    # Cattura solo post dei canali
    app.add_handler(
        MessageHandler(filters.ChatType.CHANNEL, channel_post_handler)
    )

    # Avvia health server
    threading.Thread(target=run_http_server, daemon=True).start()

    # Avvia polling
    app.run_polling()

if __name__ == "__main__":
    main()
